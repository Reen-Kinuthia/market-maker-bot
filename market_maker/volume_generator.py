"""
volume_generator.py — Controlled volume generation.

Places small randomised market/limit orders on the primary exchange to
generate organic-looking volume at or near the target price.

⚠️  IMPORTANT: Always verify this is permitted by the exchange's Terms of Service
    before enabling.  Wash-trading is prohibited on most regulated venues.
    Use this ONLY for legitimate liquidity provision or testing purposes.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import List

from .config import VolumeConfig
from .exchange import ExchangeClient, Order

log = logging.getLogger(__name__)


@dataclass
class VolumeStats:
    total_buy_volume: float = 0.0
    total_sell_volume: float = 0.0
    trade_count: int = 0
    last_trade_time: float = field(default_factory=time.monotonic)

    @property
    def total_volume(self) -> float:
        return self.total_buy_volume + self.total_sell_volume


class VolumeGenerator:
    """
    Generates volume by placing alternating small limit orders near mid-price.

    Strategy
    --------
    - Randomly chooses buy or sell side (weighted by inventory skew)
    - Places a limit order 0-0.5 basis points inside the spread
    - Immediately places a matching order on the other side (cross the book)
    - Both orders are tracked and reported
    """

    def __init__(
        self,
        client: ExchangeClient,
        cfg: VolumeConfig,
        symbol: str,
    ):
        self._client = client
        self._cfg = cfg
        self._symbol = symbol
        self._stats = VolumeStats()
        self._active_volume_orders: List[Order] = []
        self._running = False
        self._task: asyncio.Task | None = None

    # ──────────────────────────────────────────────
    #  Lifecycle
    # ──────────────────────────────────────────────

    def start(self, mid_price_getter) -> None:
        """
        Start the volume generation loop.

        Parameters
        ----------
        mid_price_getter    Async callable returning the current mid price.
        """
        if not self._cfg.enabled:
            log.info("[VolumeGen] Disabled by config.")
            return
        self._running = True
        self._mid_getter = mid_price_getter
        self._task = asyncio.create_task(self._loop(), name="volume-generator")
        log.info("[VolumeGen] Started (interval=%.1fs, size=%.4f–%.4f).",
                 self._cfg.interval, self._cfg.min_size, self._cfg.max_size)

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        log.info("[VolumeGen] Stopped. Total volume: %.6f", self._stats.total_volume)

    # ──────────────────────────────────────────────
    #  Core loop
    # ──────────────────────────────────────────────

    async def _loop(self) -> None:
        while self._running:
            try:
                jitter = random.uniform(-self._cfg.interval * 0.2,
                                        self._cfg.interval * 0.2)
                await asyncio.sleep(max(1.0, self._cfg.interval + jitter))
                await self._execute_volume_trade()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.error("[VolumeGen] Unexpected error: %s", exc, exc_info=True)
                await asyncio.sleep(5)

    async def _execute_volume_trade(self) -> None:
        mid = await self._mid_getter()
        if mid is None or mid <= 0:
            log.warning("[VolumeGen] Invalid mid price; skipping volume trade.")
            return

        size = random.uniform(self._cfg.min_size, self._cfg.max_size)
        # Tiny offset so both sides don't collide at exactly mid
        offset_fraction = random.uniform(0.00005, 0.0005)  # 0.5–5 bps

        buy_price = round(mid * (1 - offset_fraction), 8)
        sell_price = round(mid * (1 + offset_fraction), 8)

        log.info(
            "[VolumeGen] Generating volume: size=%.6f buy=%.4f sell=%.4f mid=%.4f",
            size, buy_price, sell_price, mid,
        )

        try:
            # Place buy then sell — forms a wash if both fill, or adds depth
            buy_order = await self._client.place_limit_order(
                self._symbol, "buy", size, buy_price
            )
            sell_order = await self._client.place_limit_order(
                self._symbol, "sell", size, sell_price
            )

            self._active_volume_orders.extend([buy_order, sell_order])
            self._stats.trade_count += 1
            self._stats.total_buy_volume += size
            self._stats.total_sell_volume += size
            self._stats.last_trade_time = time.monotonic()

            # Cancel after a short window to avoid clogging the book
            await asyncio.sleep(random.uniform(1.0, 3.0))
            await self._cleanup_volume_orders()

        except Exception as exc:
            log.error("[VolumeGen] Volume trade failed: %s", exc)

    async def _cleanup_volume_orders(self) -> None:
        still_open: List[Order] = []
        for order in self._active_volume_orders:
            cancelled = await self._client.cancel_order(order.id, self._symbol)
            if not cancelled:
                still_open.append(order)
        self._active_volume_orders = still_open

    # ──────────────────────────────────────────────
    #  Stats
    # ──────────────────────────────────────────────

    @property
    def stats(self) -> VolumeStats:
        return self._stats
