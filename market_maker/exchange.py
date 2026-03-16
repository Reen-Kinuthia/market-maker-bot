"""
exchange.py — Async ccxt exchange wrapper.

Wraps ccxt.async_support exchanges and exposes a clean interface used by
the rest of the bot.  Supports dry-run mode (no real orders sent).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import ccxt.async_support as ccxt

from .config import ExchangeConfig

log = logging.getLogger(__name__)


@dataclass
class Ticker:
    bid: float
    ask: float
    last: float
    mid: float = field(init=False)

    def __post_init__(self):
        self.mid = (self.bid + self.ask) / 2


@dataclass
class Order:
    id: str
    symbol: str
    side: str       # "buy" | "sell"
    price: float
    amount: float
    status: str     # "open" | "closed" | "canceled"
    raw: Dict[str, Any] = field(default_factory=dict)


class ExchangeClient:
    """
    Thin async wrapper around a ccxt exchange.

    Parameters
    ----------
    cfg         ExchangeConfig instance
    dry_run     When True no real orders are placed; a fake order id is returned.
    """

    def __init__(self, cfg: ExchangeConfig, dry_run: bool = True):
        self._cfg = cfg
        self.dry_run = dry_run
        self._exchange: ccxt.Exchange = self._build_exchange()
        self._dry_orders: Dict[str, Order] = {}  # simulated order book
        self._dry_counter = 0

    # ──────────────────────────────────────────────
    #  Lifecycle
    # ──────────────────────────────────────────────

    def _build_exchange(self) -> ccxt.Exchange:
        exchange_class = getattr(ccxt, self._cfg.exchange_id, None)
        if exchange_class is None:
            raise ValueError(f"Exchange '{self._cfg.exchange_id}' not found in ccxt.")

        params: Dict[str, Any] = {
            "enableRateLimit": True,
        }
        if self._cfg.api_key:
            params["apiKey"] = self._cfg.api_key
        if self._cfg.api_secret:
            params["secret"] = self._cfg.api_secret
        if self._cfg.passphrase:
            params["password"] = self._cfg.passphrase

        return exchange_class(params)

    async def load_markets(self) -> None:
        await self._exchange.load_markets()
        log.info("[%s] Markets loaded.", self._cfg.exchange_id)

    async def close(self) -> None:
        await self._exchange.close()

    # ──────────────────────────────────────────────
    #  Market data
    # ──────────────────────────────────────────────

    async def fetch_ticker(self, symbol: str) -> Ticker:
        raw = await self._exchange.fetch_ticker(symbol)
        bid = float(raw.get("bid") or raw.get("last") or 0)
        ask = float(raw.get("ask") or raw.get("last") or 0)
        last = float(raw.get("last") or 0)
        return Ticker(bid=bid, ask=ask, last=last)

    async def fetch_order_book(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        return await self._exchange.fetch_order_book(symbol, limit)

    # ──────────────────────────────────────────────
    #  Account
    # ──────────────────────────────────────────────

    async def fetch_balance(self) -> Dict[str, float]:
        """Returns {currency: free_amount}."""
        if self.dry_run:
            return {"BTC": 1.0, "ETH": 10.0, "USDT": 10000.0}
        raw = await self._exchange.fetch_balance()
        return {k: float(v["free"]) for k, v in raw.items()
                if isinstance(v, dict) and v.get("free") is not None}

    # ──────────────────────────────────────────────
    #  Order management
    # ──────────────────────────────────────────────

    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
    ) -> Order:
        if self.dry_run:
            return self._dry_place(symbol, side, amount, price)

        try:
            raw = await self._exchange.create_limit_order(symbol, side, amount, price)
            order = Order(
                id=str(raw["id"]),
                symbol=symbol,
                side=side,
                price=price,
                amount=amount,
                status=raw.get("status", "open"),
                raw=raw,
            )
            log.info("[%s] Placed %s limit %s @ %s  id=%s",
                     self._cfg.exchange_id, side, amount, price, order.id)
            return order
        except ccxt.BaseError as exc:
            log.error("[%s] Order placement failed: %s", self._cfg.exchange_id, exc)
            raise

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        if self.dry_run:
            self._dry_orders.pop(order_id, None)
            log.debug("[DRY-RUN] Cancelled order %s", order_id)
            return True

        try:
            await self._exchange.cancel_order(order_id, symbol)
            log.info("[%s] Cancelled order %s", self._cfg.exchange_id, order_id)
            return True
        except ccxt.OrderNotFound:
            log.warning("[%s] Order %s not found (already filled/cancelled).",
                        self._cfg.exchange_id, order_id)
            return False
        except ccxt.BaseError as exc:
            log.error("[%s] Cancel failed: %s", self._cfg.exchange_id, exc)
            return False

    async def cancel_all_orders(self, symbol: str) -> int:
        if self.dry_run:
            count = len(self._dry_orders)
            self._dry_orders.clear()
            return count

        try:
            open_orders = await self._exchange.fetch_open_orders(symbol)
            tasks = [self.cancel_order(o["id"], symbol) for o in open_orders]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            cancelled = sum(1 for r in results if r is True)
            log.info("[%s] Cancelled %d/%d orders.", self._cfg.exchange_id,
                     cancelled, len(tasks))
            return cancelled
        except ccxt.BaseError as exc:
            log.error("[%s] cancel_all_orders failed: %s", self._cfg.exchange_id, exc)
            return 0

    async def fetch_open_orders(self, symbol: str) -> List[Order]:
        if self.dry_run:
            return list(self._dry_orders.values())

        raw_list = await self._exchange.fetch_open_orders(symbol)
        return [
            Order(
                id=str(r["id"]),
                symbol=symbol,
                side=r["side"],
                price=float(r["price"]),
                amount=float(r["amount"]),
                status=r.get("status", "open"),
                raw=r,
            )
            for r in raw_list
        ]

    # ──────────────────────────────────────────────
    #  Dry-run helpers
    # ──────────────────────────────────────────────

    def _dry_place(self, symbol: str, side: str, amount: float, price: float) -> Order:
        self._dry_counter += 1
        oid = f"dry-{self._dry_counter}"
        order = Order(id=oid, symbol=symbol, side=side,
                      price=price, amount=amount, status="open")
        self._dry_orders[oid] = order
        log.debug("[DRY-RUN] %s %s %s @ %s  id=%s", side, amount, symbol, price, oid)
        return order

    @property
    def exchange_id(self) -> str:
        return self._cfg.exchange_id
