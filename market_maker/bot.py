"""
bot.py — Main market making bot orchestrator.

Wires together:
  ExchangeClient   → place/cancel orders on primary exchange
  PriceCorrelator  → blend reference exchange price with target
  MarketMakingStrategy → compute bid/ask grids
  OrderManager     → track live orders and reconcile fills
  VolumeGenerator  → optional volume generation
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
import time
from typing import Optional

from .config import BotConfig
from .exchange import ExchangeClient
from .order_manager import OrderManager
from .price_correlator import PriceCorrelator
from .strategy import Inventory, MarketMakingStrategy
from .volume_generator import VolumeGenerator

log = logging.getLogger(__name__)


class MarketMakerBot:
    """
    Top-level bot orchestrator.

    Usage
    -----
    bot = MarketMakerBot(config)
    await bot.run()          # blocks until stopped
    """

    def __init__(self, cfg: BotConfig):
        self._cfg = cfg
        self._running = False

        # Exchange clients
        self._primary = ExchangeClient(cfg.primary, dry_run=cfg.dry_run)
        self._reference = ExchangeClient(cfg.reference, dry_run=True)  # ref = read-only

        # Components
        self._correlator = PriceCorrelator(
            self._reference, cfg.correlation, cfg.strategy.symbol
        )
        self._strategy = MarketMakingStrategy(cfg.strategy)
        self._order_mgr = OrderManager(self._primary, cfg.strategy.symbol)
        self._volume_gen = VolumeGenerator(
            self._primary, cfg.volume, cfg.strategy.symbol
        )

        # Stats
        self._cycle_count = 0
        self._start_time = 0.0

    # ──────────────────────────────────────────────
    #  Lifecycle
    # ──────────────────────────────────────────────

    async def run(self) -> None:
        self._running = True
        self._start_time = time.monotonic()

        log.info("═" * 60)
        log.info("  Market Maker Bot starting")
        log.info("  Symbol:   %s", self._cfg.strategy.symbol)
        log.info("  Exchange: %s → %s",
                 self._cfg.primary.exchange_id,
                 self._cfg.reference.exchange_id)
        log.info("  DRY RUN:  %s", self._cfg.dry_run)
        log.info("  Spread:   %.3f%%", self._cfg.strategy.spread * 100)
        log.info("  Levels:   %d", self._cfg.strategy.levels)
        log.info("═" * 60)

        # Register signal handlers for graceful shutdown
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._signal_handler)

        try:
            await self._setup()
            await self._main_loop()
        except Exception as exc:
            log.error("Fatal error: %s", exc, exc_info=True)
        finally:
            await self._teardown()

    async def stop(self) -> None:
        log.info("Stop requested.")
        self._running = False

    # ──────────────────────────────────────────────
    #  Setup / Teardown
    # ──────────────────────────────────────────────

    async def _setup(self) -> None:
        log.info("Loading markets…")
        await asyncio.gather(
            self._primary.load_markets(),
            self._reference.load_markets(),
        )

        # Initial reference price fetch
        await self._correlator.update()

        # Start volume generator (no-op if disabled)
        self._volume_gen.start(mid_price_getter=self._get_current_mid)

        log.info("Setup complete.")

    async def _teardown(self) -> None:
        log.info("Shutting down…")
        self._volume_gen.stop()

        log.info("Cancelling all open orders…")
        await self._order_mgr.cancel_all()

        await asyncio.gather(
            self._primary.close(),
            self._reference.close(),
            return_exceptions=True,
        )

        elapsed = time.monotonic() - self._start_time
        log.info(
            "Bot stopped after %d cycles (%.1f s).  Volume stats: %s",
            self._cycle_count,
            elapsed,
            self._volume_gen.stats,
        )

    # ──────────────────────────────────────────────
    #  Main loop
    # ──────────────────────────────────────────────

    async def _main_loop(self) -> None:
        while self._running:
            cycle_start = time.monotonic()
            try:
                await self._cycle()
            except Exception as exc:
                log.error("Cycle error: %s", exc, exc_info=True)

            elapsed = time.monotonic() - cycle_start
            sleep_time = max(0.1, self._cfg.strategy.refresh_interval - elapsed)
            log.debug("Cycle %d done in %.2fs; sleeping %.2fs.",
                      self._cycle_count, elapsed, sleep_time)
            await asyncio.sleep(sleep_time)

    async def _cycle(self) -> None:
        self._cycle_count += 1
        symbol = self._cfg.strategy.symbol

        # 1. Refresh reference price
        await self._correlator.update()

        # 2. Fetch primary ticker and balance
        primary_ticker = await self._primary.fetch_ticker(symbol)
        balance = await self._primary.fetch_balance()

        base_currency = symbol.split("/")[0]
        quote_currency = symbol.split("/")[1]
        inventory = Inventory(
            base=balance.get(base_currency, 0.0),
            quote=balance.get(quote_currency, 0.0),
        )

        # 3. Determine target mid price
        if self._cfg.strategy.target_price:
            raw_target = self._cfg.strategy.target_price
        else:
            raw_target = primary_ticker.mid

        blended_mid, confidence = self._correlator.blend(raw_target)

        # 4. Deviation guard
        if not self._correlator.check_deviation(blended_mid):
            log.warning("Cycle %d: Price deviation too large — skipping order refresh.",
                        self._cycle_count)
            return

        # 5. Compute grid
        bid_levels, ask_levels = self._strategy.compute_grid(blended_mid, inventory)

        # 6. Cancel stale orders, place new ones
        await self._order_mgr.cancel_stale(
            [lv.price for lv in bid_levels],
            [lv.price for lv in ask_levels],
        )
        await self._order_mgr.place_grid(
            [lv.to_dict() for lv in bid_levels],
            [lv.to_dict() for lv in ask_levels],
        )

        # 7. Reconcile fills
        filled = await self._order_mgr.reconcile()
        if filled:
            log.info("Cycle %d: %d orders filled.", self._cycle_count, len(filled))

        # 8. Status log
        log.info(
            "Cycle %d | mid=%.4f blended=%.4f conf=%.2f | "
            "inv %s=%.6f %s=%.2f | %s",
            self._cycle_count,
            primary_ticker.mid,
            blended_mid,
            confidence,
            base_currency, inventory.base,
            quote_currency, inventory.quote,
            self._order_mgr.summary(),
        )

        # Store current mid for volume generator
        self._current_mid = blended_mid

    # ──────────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────────

    async def _get_current_mid(self) -> Optional[float]:
        return getattr(self, "_current_mid", None)

    def _signal_handler(self, signum, frame) -> None:
        log.info("Signal %s received — stopping.", signum)
        self._running = False
