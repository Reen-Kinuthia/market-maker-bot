"""
price_correlator.py — Cross-exchange price correlation engine.

Blends the local target price with the reference exchange's mid-price so that
our quotes stay in line with the broader market.

                 blended = weight * ref_mid  +  (1 - weight) * target
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Deque, Optional, Tuple

from .config import CorrelationConfig
from .exchange import ExchangeClient, Ticker

log = logging.getLogger(__name__)

# Rolling window size for EWMA smoothing
_WINDOW = 20


class PriceCorrelator:
    """
    Fetches the reference exchange price and blends it with the local target.

    Parameters
    ----------
    ref_client      ExchangeClient connected to the reference exchange
    cfg             CorrelationConfig
    symbol          Trading pair (must be the same on both exchanges)
    """

    def __init__(
        self,
        ref_client: ExchangeClient,
        cfg: CorrelationConfig,
        symbol: str,
    ):
        self._client = ref_client
        self._cfg = cfg
        self._symbol = symbol

        self._ref_prices: Deque[float] = deque(maxlen=_WINDOW)
        self._last_ref_ticker: Optional[Ticker] = None
        self._last_updated: float = 0.0
        self._lock = asyncio.Lock()

    # ──────────────────────────────────────────────
    #  Public API
    # ──────────────────────────────────────────────

    async def update(self) -> Optional[Ticker]:
        """Fetch latest ticker from the reference exchange."""
        async with self._lock:
            try:
                ticker = await self._client.fetch_ticker(self._symbol)
                self._ref_prices.append(ticker.mid)
                self._last_ref_ticker = ticker
                self._last_updated = time.monotonic()
                log.debug("[Correlator] Ref price updated: mid=%.4f bid=%.4f ask=%.4f",
                          ticker.mid, ticker.bid, ticker.ask)
                return ticker
            except Exception as exc:
                log.warning("[Correlator] Failed to fetch reference price: %s", exc)
                return None

    def blend(self, target_price: float) -> Tuple[float, float]:
        """
        Compute blended mid price and confidence score.

        Returns
        -------
        (blended_mid, confidence)
            confidence  1.0 if reference data is fresh, decays over time.
        """
        ref_mid = self.smoothed_ref_price
        if ref_mid is None:
            return target_price, 0.0

        confidence = self._confidence()
        effective_weight = self._cfg.weight * confidence
        blended = effective_weight * ref_mid + (1.0 - effective_weight) * target_price

        log.debug(
            "[Correlator] blend: target=%.4f ref=%.4f weight=%.2f "
            "confidence=%.2f → blended=%.4f",
            target_price, ref_mid, self._cfg.weight, confidence, blended,
        )
        return blended, confidence

    def check_deviation(self, our_price: float) -> bool:
        """
        Returns True if our price is within acceptable deviation of reference.
        Returns False (halt signal) if deviation exceeds max_deviation.
        """
        ref = self.smoothed_ref_price
        if ref is None:
            return True  # no reference data → don't halt

        deviation = abs(our_price - ref) / ref
        if deviation > self._cfg.max_deviation:
            log.warning(
                "[Correlator] DEVIATION ALERT: our=%.4f ref=%.4f dev=%.2f%% > limit=%.2f%%",
                our_price, ref, deviation * 100, self._cfg.max_deviation * 100,
            )
            return False
        return True

    @property
    def smoothed_ref_price(self) -> Optional[float]:
        """Exponentially-weighted moving average of recent reference prices."""
        if not self._ref_prices:
            return None
        prices = list(self._ref_prices)
        alpha = 2 / (len(prices) + 1)
        ewma = prices[0]
        for p in prices[1:]:
            ewma = alpha * p + (1 - alpha) * ewma
        return ewma

    @property
    def last_ticker(self) -> Optional[Ticker]:
        return self._last_ref_ticker

    @property
    def spread_on_reference(self) -> Optional[float]:
        """Current bid/ask spread on the reference exchange as a fraction."""
        t = self._last_ref_ticker
        if t is None or t.mid == 0:
            return None
        return (t.ask - t.bid) / t.mid

    # ──────────────────────────────────────────────
    #  Internals
    # ──────────────────────────────────────────────

    def _confidence(self) -> float:
        """Decay confidence if reference data is stale (> 30 s old)."""
        if self._last_updated == 0:
            return 0.0
        age = time.monotonic() - self._last_updated
        if age < 30:
            return 1.0
        # Linear decay: 0 at 5 minutes
        return max(0.0, 1.0 - (age - 30) / 270)
