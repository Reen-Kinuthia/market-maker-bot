"""
order_manager.py — Tracks active orders and reconciles them against the exchange.

Keeps an in-process registry of open orders so we know which ones to cancel
before placing a fresh grid.  Reconciles with the exchange to handle fills that
happened between refresh cycles.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .exchange import ExchangeClient, Order

log = logging.getLogger(__name__)


@dataclass
class OrderBook:
    """Live snapshot of our orders on one exchange."""
    bids: List[Order] = field(default_factory=list)
    asks: List[Order] = field(default_factory=list)

    @property
    def all(self) -> List[Order]:
        return self.bids + self.asks

    @property
    def ids(self) -> List[str]:
        return [o.id for o in self.all]


class OrderManager:
    """
    Manages the full lifecycle of our maker orders.

    Usage
    -----
    manager = OrderManager(client, symbol)
    await manager.cancel_all()
    await manager.place_grid(bid_levels, ask_levels)
    await manager.reconcile()   # detect and remove filled orders
    """

    def __init__(self, client: ExchangeClient, symbol: str):
        self._client = client
        self._symbol = symbol
        self._book: OrderBook = OrderBook()
        self._lock = asyncio.Lock()

    # ──────────────────────────────────────────────
    #  Public API
    # ──────────────────────────────────────────────

    async def cancel_all(self) -> None:
        async with self._lock:
            count = await self._client.cancel_all_orders(self._symbol)
            self._book = OrderBook()
            log.info("[OrderManager] Cancelled %d orders.", count)

    async def cancel_stale(self, fresh_bid_prices: List[float],
                           fresh_ask_prices: List[float]) -> None:
        """Cancel only orders whose price is no longer in the fresh grid."""
        async with self._lock:
            fresh_bid_set = set(fresh_bid_prices)
            fresh_ask_set = set(fresh_ask_prices)
            to_cancel: List[Order] = []

            surviving_bids, surviving_asks = [], []
            for o in self._book.bids:
                if o.price not in fresh_bid_set:
                    to_cancel.append(o)
                else:
                    surviving_bids.append(o)
            for o in self._book.asks:
                if o.price not in fresh_ask_set:
                    to_cancel.append(o)
                else:
                    surviving_asks.append(o)

            tasks = [self._client.cancel_order(o.id, self._symbol) for o in to_cancel]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                log.info("[OrderManager] Cancelled %d stale orders.", len(tasks))

            self._book.bids = surviving_bids
            self._book.asks = surviving_asks

    async def place_grid(
        self,
        bid_levels: List[Dict],
        ask_levels: List[Dict],
    ) -> None:
        """
        Place a grid of limit orders.

        Parameters
        ----------
        bid_levels  List of {"price": float, "amount": float}
        ask_levels  List of {"price": float, "amount": float}
        """
        async with self._lock:
            existing_bid_prices = {o.price for o in self._book.bids}
            existing_ask_prices = {o.price for o in self._book.asks}

            bid_tasks = [
                self._place_if_missing(lv, "buy", existing_bid_prices)
                for lv in bid_levels
            ]
            ask_tasks = [
                self._place_if_missing(lv, "sell", existing_ask_prices)
                for lv in ask_levels
            ]
            results = await asyncio.gather(*(bid_tasks + ask_tasks),
                                           return_exceptions=True)

            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    side = "buy" if i < len(bid_tasks) else "sell"
                    log.error("[OrderManager] Failed to place %s order: %s", side, res)
                elif res is not None:
                    if res.side == "buy":
                        self._book.bids.append(res)
                    else:
                        self._book.asks.append(res)

    async def reconcile(self) -> List[Order]:
        """
        Fetch open orders from exchange and prune our book.
        Returns filled orders that were removed.
        """
        async with self._lock:
            live_orders = await self._client.fetch_open_orders(self._symbol)
            live_ids = {o.id for o in live_orders}
            filled: List[Order] = []

            surviving_bids, surviving_asks = [], []
            for o in self._book.bids:
                if o.id in live_ids:
                    surviving_bids.append(o)
                else:
                    filled.append(o)
                    log.info("[OrderManager] Bid filled/cancelled: %s @ %s",
                             o.amount, o.price)
            for o in self._book.asks:
                if o.id in live_ids:
                    surviving_asks.append(o)
                else:
                    filled.append(o)
                    log.info("[OrderManager] Ask filled/cancelled: %s @ %s",
                             o.amount, o.price)

            self._book.bids = surviving_bids
            self._book.asks = surviving_asks
            return filled

    # ──────────────────────────────────────────────
    #  Reporting
    # ──────────────────────────────────────────────

    @property
    def book(self) -> OrderBook:
        return self._book

    def summary(self) -> str:
        bids = ", ".join(f"{o.price}({o.amount})" for o in self._book.bids)
        asks = ", ".join(f"{o.price}({o.amount})" for o in self._book.asks)
        return f"BIDS[{bids}]  ASKS[{asks}]"

    # ──────────────────────────────────────────────
    #  Internals
    # ──────────────────────────────────────────────

    async def _place_if_missing(
        self,
        level: Dict,
        side: str,
        existing_prices: set,
    ) -> Optional[Order]:
        if level["price"] in existing_prices:
            log.debug("[OrderManager] Skipping existing %s @ %s", side, level["price"])
            return None
        return await self._client.place_limit_order(
            self._symbol, side, level["amount"], level["price"]
        )
