"""
strategy.py — Core market-making strategy.

Computes bid and ask grids around a target mid-price, applying:
  • Multi-level laddering
  • Inventory-based skew (reduces exposure when over-positioned)
  • Blended price from cross-exchange correlation
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .config import StrategyConfig

log = logging.getLogger(__name__)


@dataclass
class GridLevel:
    price: float
    amount: float
    side: str   # "buy" | "sell"
    level: int  # 0 = tightest, N = outermost

    def to_dict(self) -> Dict:
        return {"price": self.price, "amount": self.amount}


@dataclass
class Inventory:
    base: float     # e.g. BTC held
    quote: float    # e.g. USDT held

    def skew_factor(
        self,
        mid_price: float,
        max_base: float,
        max_quote: float,
    ) -> float:
        """
        Returns a value in [-1, 1] indicating inventory imbalance.
         +1 → heavy in quote (want to buy)
         -1 → heavy in base  (want to sell)
          0 → balanced
        """
        base_value = self.base * mid_price
        total_value = base_value + self.quote
        if total_value == 0:
            return 0.0

        base_ratio = base_value / total_value
        target_ratio = 0.5  # balanced = 50/50

        # Normalise against max position constraints
        max_base_value = max_base * mid_price
        max_quote_value = max_quote
        max_total = max_base_value + max_quote_value
        if max_total == 0:
            return 0.0

        imbalance = target_ratio - base_ratio  # positive → need more base
        # Clamp to [-1, 1]
        return max(-1.0, min(1.0, imbalance * 2))


class MarketMakingStrategy:
    """
    Produces bid/ask grid levels given a mid price and current inventory.

    Grid construction
    -----------------
    For N levels on each side:
      level 0 price   = mid ± (spread/2)
      level k price   = mid ± (spread/2 + k * level_spacing)
      level k amount  = base_size * multiplier^k

    Inventory skew adjusts the mid price slightly so the bot naturally
    reduces inventory exposure without hard stops.
    """

    def __init__(self, cfg: StrategyConfig):
        self._cfg = cfg

    # ──────────────────────────────────────────────
    #  Public API
    # ──────────────────────────────────────────────

    def compute_grid(
        self,
        mid_price: float,
        inventory: Optional[Inventory] = None,
    ) -> Tuple[List[GridLevel], List[GridLevel]]:
        """
        Compute bid and ask grid levels.

        Returns
        -------
        (bid_levels, ask_levels)  sorted by price (bids descending, asks ascending)
        """
        skew = 0.0
        if self._cfg.inventory_skew and inventory is not None:
            skew = inventory.skew_factor(
                mid_price,
                self._cfg.max_position_base,
                self._cfg.max_position_quote,
            )

        # Skew shifts the reference mid price slightly
        skewed_mid = mid_price * (1 + skew * self._cfg.spread * 0.5)
        log.debug("[Strategy] mid=%.4f skew=%.4f skewed_mid=%.4f",
                  mid_price, skew, skewed_mid)

        half_spread = self._cfg.spread / 2

        bids: List[GridLevel] = []
        asks: List[GridLevel] = []

        for i in range(self._cfg.levels):
            extra_spread = i * self._cfg.level_spacing
            size = self._cfg.order_size * (self._cfg.level_size_multiplier ** i)

            # Bid side — inventory skew increases size when we want more base
            bid_size_mult = 1.0 + max(0.0, skew) * 0.5
            ask_size_mult = 1.0 + max(0.0, -skew) * 0.5

            bid_price = self._round_price(
                skewed_mid * (1 - half_spread - extra_spread)
            )
            ask_price = self._round_price(
                skewed_mid * (1 + half_spread + extra_spread)
            )

            bids.append(GridLevel(
                price=bid_price,
                amount=round(size * bid_size_mult, 8),
                side="buy",
                level=i,
            ))
            asks.append(GridLevel(
                price=ask_price,
                amount=round(size * ask_size_mult, 8),
                side="sell",
                level=i,
            ))

        bids.sort(key=lambda x: x.price, reverse=True)  # highest bid first
        asks.sort(key=lambda x: x.price)                 # lowest ask first

        self._log_grid(bids, asks, skewed_mid)
        return bids, asks

    def compute_target_mid(
        self,
        blended_price: float,
        current_ticker_mid: Optional[float] = None,
    ) -> float:
        """
        Determine the mid price to use for grid placement.
        Falls back to the live ticker if blended price is unavailable.
        """
        if blended_price and blended_price > 0:
            return blended_price
        if current_ticker_mid and current_ticker_mid > 0:
            log.warning("[Strategy] No blended price; using live ticker mid.")
            return current_ticker_mid
        raise ValueError("Cannot determine mid price — no price source available.")

    # ──────────────────────────────────────────────
    #  Internals
    # ──────────────────────────────────────────────

    def _round_price(self, price: float) -> float:
        # Round to 2 decimal places by default; could be exchange-specific
        return round(price, 2)

    def _log_grid(
        self,
        bids: List[GridLevel],
        asks: List[GridLevel],
        mid: float,
    ) -> None:
        bid_str = "  ".join(f"[{g.level}] {g.price} x {g.amount}" for g in bids)
        ask_str = "  ".join(f"[{g.level}] {g.price} x {g.amount}" for g in asks)
        log.info("[Strategy] Mid=%.4f  BIDS: %s  ASKS: %s", mid, bid_str, ask_str)

    # ──────────────────────────────────────────────
    #  Risk checks
    # ──────────────────────────────────────────────

    def check_position_limits(self, inventory: Inventory, mid_price: float) -> bool:
        """Returns False if position limits are breached."""
        if inventory.base > self._cfg.max_position_base:
            log.warning(
                "[Strategy] Base position %.6f exceeds max %.6f. Halting bids.",
                inventory.base, self._cfg.max_position_base,
            )
            return False
        if inventory.quote > self._cfg.max_position_quote:
            log.warning(
                "[Strategy] Quote position %.2f exceeds max %.2f. Halting asks.",
                inventory.quote, self._cfg.max_position_quote,
            )
            return False
        return True
