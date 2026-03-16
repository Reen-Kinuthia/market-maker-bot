"""
simulator.py — Generates realistic market data for dry-run / demo mode.

Produces:
  - Brownian-motion price walk anchored to a starting price
  - Bid/ask grid orders around mid price
  - Simulated balances that update on fills
  - Organic trade feed (random market takers)
"""
from __future__ import annotations

import math
import random
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional


# ────────────────────────────────────────────────────
#  Data shapes
# ────────────────────────────────────────────────────

@dataclass
class PricePoint:
    timestamp: float
    mid: float
    bid: float
    ask: float
    ref_mid: float   # reference exchange price


@dataclass
class SimOrder:
    id: str
    side: str        # "buy" | "sell"
    price: float
    amount: float
    filled: float = 0.0
    status: str = "open"   # "open" | "filled" | "cancelled"
    created_at: float = field(default_factory=time.time)
    is_organic: bool = False   # organic = from market takers

    @property
    def remaining(self) -> float:
        return self.amount - self.filled

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "side": self.side,
            "price": self.price,
            "amount": self.amount,
            "filled": self.filled,
            "remaining": self.remaining,
            "status": self.status,
            "created_at": self.created_at,
            "is_organic": self.is_organic,
        }


@dataclass
class Trade:
    id: str
    side: str
    price: float
    amount: float
    timestamp: float
    is_organic: bool

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "side": self.side,
            "price": self.price,
            "amount": self.amount,
            "timestamp": self.timestamp,
            "is_organic": self.is_organic,
        }


# ────────────────────────────────────────────────────
#  Simulator
# ────────────────────────────────────────────────────

class MarketSimulator:
    """
    Stateful market simulator.  Call tick() every second to advance.
    """

    def __init__(
        self,
        symbol: str = "BTC/USDT",
        start_price: float = 65000.0,
        spread_frac: float = 0.002,
        levels: int = 3,
        level_spacing: float = 0.001,
        base_order_size: float = 0.001,
        size_multiplier: float = 1.5,
    ):
        self.symbol = symbol
        self._spread = spread_frac
        self._levels = levels
        self._level_spacing = level_spacing
        self._base_size = base_order_size
        self._size_mult = size_multiplier

        # Price state
        self._mid = start_price
        self._ref_mid = start_price * random.uniform(0.9998, 1.0002)
        self._vol = 0.0003         # per-tick volatility (≈0.03%)
        self._drift = 0.0

        # Balances
        base_sym = symbol.split("/")[0]
        quote_sym = symbol.split("/")[1]
        self.balances: Dict[str, float] = {
            base_sym: 0.5,
            quote_sym: 15000.0,
        }

        # Order book
        self.open_orders: Dict[str, SimOrder] = {}
        self.recent_trades: Deque[Trade] = deque(maxlen=100)
        self.price_history: Deque[PricePoint] = deque(maxlen=500)

        # Counters
        self._cycle = 0
        self._refresh_every = 10   # rebuild grid every N ticks
        self._organic_interval = random.randint(3, 8)
        self._ticks_since_organic = 0

        # Build initial grid
        self._rebuild_grid()

    # ──────────────────────────────────────────────
    #  Public
    # ──────────────────────────────────────────────

    def tick(self) -> dict:
        """Advance one tick and return full state snapshot."""
        self._cycle += 1
        self._advance_price()
        self._maybe_fill_organic()
        self._maybe_fill_maker()

        if self._cycle % self._refresh_every == 0:
            self._rebuild_grid()

        snap = self._snapshot()
        self.price_history.append(PricePoint(
            timestamp=time.time(),
            mid=self._mid,
            bid=self._bid,
            ask=self._ask,
            ref_mid=self._ref_mid,
        ))
        return snap

    @property
    def base_currency(self) -> str:
        return self.symbol.split("/")[0]

    @property
    def quote_currency(self) -> str:
        return self.symbol.split("/")[1]

    # ──────────────────────────────────────────────
    #  Price walk
    # ──────────────────────────────────────────────

    def _advance_price(self) -> None:
        # Geometric Brownian Motion tick
        shock = random.gauss(0, 1) * self._vol
        self._drift = self._drift * 0.95 + random.gauss(0, 0.0001)
        self._mid = self._mid * math.exp(self._drift + shock)

        # Reference exchange tracks with slight lag + independent noise
        ref_shock = random.gauss(0, 1) * self._vol * 0.8
        ref_lag = (self._mid - self._ref_mid) * 0.3
        self._ref_mid = self._ref_mid * math.exp(ref_shock * 0.001) + ref_lag * 0.01

        half_spread = self._mid * self._spread / 2
        self._bid = round(self._mid - half_spread, 2)
        self._ask = round(self._mid + half_spread, 2)

    # ──────────────────────────────────────────────
    #  Grid management
    # ──────────────────────────────────────────────

    def _rebuild_grid(self) -> None:
        # Cancel old maker orders
        for oid in list(self.open_orders.keys()):
            o = self.open_orders[oid]
            if not o.is_organic:
                del self.open_orders[oid]

        # Place fresh ladder
        for i in range(self._levels):
            extra = i * self._level_spacing
            size = round(self._base_size * (self._size_mult ** i), 6)

            bid_price = round(self._mid * (1 - self._spread / 2 - extra), 2)
            ask_price = round(self._mid * (1 + self._spread / 2 + extra), 2)

            self._add_order("buy", bid_price, size, organic=False)
            self._add_order("sell", ask_price, size, organic=False)

    def _add_order(self, side: str, price: float, amount: float, organic: bool) -> SimOrder:
        o = SimOrder(
            id=str(uuid.uuid4())[:8],
            side=side,
            price=price,
            amount=amount,
            is_organic=organic,
        )
        self.open_orders[o.id] = o
        return o

    # ──────────────────────────────────────────────
    #  Fill simulation
    # ──────────────────────────────────────────────

    def _maybe_fill_maker(self) -> None:
        """Randomly partially or fully fill maker orders."""
        for oid, order in list(self.open_orders.items()):
            if order.is_organic:
                continue
            # Probability of a fill depends on distance from mid
            dist = abs(order.price - self._mid) / self._mid
            prob = max(0.0, 0.08 - dist * 10)

            if random.random() < prob:
                fill_frac = random.uniform(0.3, 1.0)
                fill_qty = round(order.remaining * fill_frac, 6)
                if fill_qty < 1e-8:
                    continue
                self._execute_fill(order, fill_qty)
                if order.remaining < 1e-8:
                    order.status = "filled"
                    del self.open_orders[oid]

    def _maybe_fill_organic(self) -> None:
        """Simulate organic market takers hitting our book."""
        self._ticks_since_organic += 1
        if self._ticks_since_organic < self._organic_interval:
            return

        self._ticks_since_organic = 0
        self._organic_interval = random.randint(3, 8)

        side = random.choice(["buy", "sell"])
        size = round(random.uniform(self._base_size * 0.5, self._base_size * 3), 6)
        price = self._ask if side == "buy" else self._bid

        organic = self._add_order(side, price, size, organic=True)
        self._execute_fill(organic, size)
        organic.status = "filled"
        del self.open_orders[organic.id]

    def _execute_fill(self, order: SimOrder, qty: float) -> None:
        order.filled += qty
        base = self.base_currency
        quote = self.quote_currency

        if order.side == "buy":
            self.balances[base] = round(
                self.balances.get(base, 0) + qty, 8
            )
            self.balances[quote] = round(
                self.balances.get(quote, 0) - qty * order.price, 2
            )
        else:
            self.balances[base] = round(
                self.balances.get(base, 0) - qty, 8
            )
            self.balances[quote] = round(
                self.balances.get(quote, 0) + qty * order.price, 2
            )

        trade = Trade(
            id=str(uuid.uuid4())[:8],
            side=order.side,
            price=order.price,
            amount=qty,
            timestamp=time.time(),
            is_organic=order.is_organic,
        )
        self.recent_trades.appendleft(trade)

    # ──────────────────────────────────────────────
    #  Snapshot
    # ──────────────────────────────────────────────

    def _snapshot(self) -> dict:
        open_orders = [o.to_dict() for o in self.open_orders.values()]
        bids = sorted(
            [o for o in open_orders if o["side"] == "buy"],
            key=lambda x: -x["price"]
        )
        asks = sorted(
            [o for o in open_orders if o["side"] == "sell"],
            key=lambda x: x["price"]
        )

        price_hist = [
            {"t": p.timestamp, "mid": round(p.mid, 2),
             "bid": round(p.bid, 2), "ask": round(p.ask, 2),
             "ref": round(p.ref_mid, 2)}
            for p in self.price_history
        ]

        return {
            "type": "snapshot",
            "symbol": self.symbol,
            "cycle": self._cycle,
            "timestamp": time.time(),
            "price": {
                "mid": round(self._mid, 2),
                "bid": round(self._bid, 2),
                "ask": round(self._ask, 2),
                "ref_mid": round(self._ref_mid, 2),
                "spread_bps": round(self._spread * 10000, 1),
            },
            "balances": dict(self.balances),
            "orders": {
                "bids": bids,
                "asks": asks,
                "total": len(open_orders),
            },
            "trades": [t.to_dict() for t in list(self.recent_trades)[:20]],
            "price_history": price_hist[-200:],
            "stats": {
                "total_trades": len(self.recent_trades),
                "organic_orders": sum(
                    1 for o in self.open_orders.values() if o.is_organic
                ),
            },
        }
