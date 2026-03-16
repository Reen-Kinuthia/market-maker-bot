"""
simulator.py — Generates realistic market data for dry-run / demo mode.

Produces:
  - Price walk with optional mean-reversion to a user-set target price
  - Bid/ask grid orders with partial fill tracking
  - Simulated balances that update on fills
  - Organic trade feed (random market takers)
  - Report stats: volume, PnL, fill rate, spread revenue
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
    ref_mid: float
    target: Optional[float]


@dataclass
class SimOrder:
    id: str
    side: str
    price: float
    amount: float
    filled: float = 0.0
    status: str = "open"
    created_at: float = field(default_factory=time.time)
    is_organic: bool = False
    level: int = 0

    @property
    def remaining(self) -> float:
        return self.amount - self.filled

    @property
    def fill_pct(self) -> float:
        return (self.filled / self.amount * 100) if self.amount > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "side": self.side,
            "price": self.price,
            "amount": self.amount,
            "filled": self.filled,
            "fill_pct": round(self.fill_pct, 1),
            "remaining": self.remaining,
            "status": self.status,
            "created_at": self.created_at,
            "is_organic": self.is_organic,
            "level": self.level,
        }


@dataclass
class Trade:
    id: str
    side: str
    price: float
    amount: float
    timestamp: float
    is_organic: bool
    spread_revenue: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "side": self.side,
            "price": self.price,
            "amount": self.amount,
            "timestamp": self.timestamp,
            "is_organic": self.is_organic,
            "spread_revenue": round(self.spread_revenue, 4),
        }


# ────────────────────────────────────────────────────
#  Simulator
# ────────────────────────────────────────────────────

class MarketSimulator:
    """
    Stateful market simulator.  Call tick() every second to advance.
    Set target_price at any time to anchor price via mean reversion.
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
        target_price: Optional[float] = None,
    ):
        self.symbol = symbol
        self._spread = spread_frac
        self._levels = levels
        self._level_spacing = level_spacing
        self._base_size = base_order_size
        self._size_mult = size_multiplier
        self.target_price: Optional[float] = target_price

        # Price state
        self._mid = start_price
        self._ref_mid = start_price * random.uniform(0.9998, 1.0002)
        self._vol = 0.0003
        self._drift = 0.0

        # Balances
        base_sym = symbol.split("/")[0]
        quote_sym = symbol.split("/")[1]
        self._start_base = 0.5
        self._start_quote = 15000.0
        self.balances: Dict[str, float] = {
            base_sym: self._start_base,
            quote_sym: self._start_quote,
        }

        # Order book
        self.open_orders: Dict[str, SimOrder] = {}
        self.recent_trades: Deque[Trade] = deque(maxlen=200)
        self.price_history: Deque[PricePoint] = deque(maxlen=500)

        # Counters / stats
        self._cycle = 0
        self._refresh_every = 10
        self._organic_interval = random.randint(3, 8)
        self._ticks_since_organic = 0
        self._total_buy_volume = 0.0
        self._total_sell_volume = 0.0
        self._total_fills = 0
        self._organic_fills = 0
        self._maker_fills = 0
        self._spread_revenue = 0.0
        self._start_time = time.time()

        self._rebuild_grid()

    # ──────────────────────────────────────────────
    #  Public
    # ──────────────────────────────────────────────

    def tick(self) -> dict:
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
            target=self.target_price,
        ))
        return snap

    def set_target_price(self, price: Optional[float]) -> None:
        self.target_price = price

    @property
    def base_currency(self) -> str:
        return self.symbol.split("/")[0]

    @property
    def quote_currency(self) -> str:
        return self.symbol.split("/")[1]

    # ──────────────────────────────────────────────
    #  Price walk — with target mean reversion
    # ──────────────────────────────────────────────

    def _advance_price(self) -> None:
        shock = random.gauss(0, 1) * self._vol

        if self.target_price and self.target_price > 0:
            # Mean reversion: stronger pull when far from target
            deviation = (self.target_price - self._mid) / self._mid
            reversion = deviation * 0.08   # 8% pull per tick toward target
            self._drift = self._drift * 0.9 + reversion + random.gauss(0, 0.00005)
        else:
            self._drift = self._drift * 0.95 + random.gauss(0, 0.0001)

        self._mid = self._mid * math.exp(self._drift + shock)

        # Reference exchange — slight lag
        ref_shock = random.gauss(0, 1) * self._vol * 0.6
        ref_lag = (self._mid - self._ref_mid) * 0.25
        self._ref_mid = self._ref_mid * math.exp(ref_shock * 0.0005) + ref_lag * 0.015

        half_spread = self._mid * self._spread / 2
        self._bid = round(self._mid - half_spread, 2)
        self._ask = round(self._mid + half_spread, 2)

    # ──────────────────────────────────────────────
    #  Grid management
    # ──────────────────────────────────────────────

    def _rebuild_grid(self) -> None:
        for oid in list(self.open_orders.keys()):
            if not self.open_orders[oid].is_organic:
                del self.open_orders[oid]

        for i in range(self._levels):
            extra = i * self._level_spacing
            size = round(self._base_size * (self._size_mult ** i), 6)
            bid_price = round(self._mid * (1 - self._spread / 2 - extra), 2)
            ask_price = round(self._mid * (1 + self._spread / 2 + extra), 2)
            self._add_order("buy",  bid_price, size, organic=False, level=i)
            self._add_order("sell", ask_price, size, organic=False, level=i)

    def _add_order(self, side: str, price: float, amount: float,
                   organic: bool, level: int = 0) -> SimOrder:
        o = SimOrder(
            id=str(uuid.uuid4())[:8],
            side=side, price=price, amount=amount,
            is_organic=organic, level=level,
        )
        self.open_orders[o.id] = o
        return o

    # ──────────────────────────────────────────────
    #  Fill simulation
    # ──────────────────────────────────────────────

    def _maybe_fill_maker(self) -> None:
        for oid, order in list(self.open_orders.items()):
            if order.is_organic:
                continue
            dist = abs(order.price - self._mid) / self._mid
            prob = max(0.0, 0.08 - dist * 10)
            if random.random() < prob:
                fill_frac = random.uniform(0.3, 1.0)
                fill_qty = round(order.remaining * fill_frac, 6)
                if fill_qty < 1e-8:
                    continue
                self._execute_fill(order, fill_qty, is_maker=True)
                if order.remaining < 1e-8:
                    order.status = "filled"
                    del self.open_orders[oid]

    def _maybe_fill_organic(self) -> None:
        self._ticks_since_organic += 1
        if self._ticks_since_organic < self._organic_interval:
            return
        self._ticks_since_organic = 0
        self._organic_interval = random.randint(3, 8)

        side = random.choice(["buy", "sell"])
        size = round(random.uniform(self._base_size * 0.5, self._base_size * 3), 6)
        price = self._ask if side == "buy" else self._bid

        organic = self._add_order(side, price, size, organic=True)
        self._execute_fill(organic, size, is_maker=False)
        organic.status = "filled"
        del self.open_orders[organic.id]

    def _execute_fill(self, order: SimOrder, qty: float, is_maker: bool) -> None:
        order.filled += qty
        base = self.base_currency
        quote = self.quote_currency

        spread_rev = qty * order.price * self._spread / 2 if is_maker else 0.0

        if order.side == "buy":
            self.balances[base]  = round(self.balances.get(base, 0)  + qty, 8)
            self.balances[quote] = round(self.balances.get(quote, 0) - qty * order.price, 2)
            self._total_buy_volume += qty
        else:
            self.balances[base]  = round(self.balances.get(base, 0)  - qty, 8)
            self.balances[quote] = round(self.balances.get(quote, 0) + qty * order.price, 2)
            self._total_sell_volume += qty

        self._total_fills += 1
        self._spread_revenue += spread_rev
        if order.is_organic:
            self._organic_fills += 1
        else:
            self._maker_fills += 1

        self.recent_trades.appendleft(Trade(
            id=str(uuid.uuid4())[:8],
            side=order.side,
            price=order.price,
            amount=qty,
            timestamp=time.time(),
            is_organic=order.is_organic,
            spread_revenue=spread_rev,
        ))

    # ──────────────────────────────────────────────
    #  Snapshot
    # ──────────────────────────────────────────────

    def _snapshot(self) -> dict:
        open_orders = [o.to_dict() for o in self.open_orders.values()]
        bids = sorted([o for o in open_orders if o["side"] == "buy"],  key=lambda x: -x["price"])
        asks = sorted([o for o in open_orders if o["side"] == "sell"], key=lambda x:  x["price"])

        price_hist = [
            {"t": p.timestamp, "mid": round(p.mid, 2),
             "bid": round(p.bid, 2), "ask": round(p.ask, 2),
             "ref": round(p.ref_mid, 2),
             "target": round(p.target, 2) if p.target else None}
            for p in self.price_history
        ]

        # PnL: current portfolio value vs starting value at current mid
        base = self.base_currency
        quote = self.quote_currency
        start_value = self._start_base * self._mid + self._start_quote
        curr_value  = self.balances.get(base, 0) * self._mid + self.balances.get(quote, 0)
        pnl = curr_value - start_value
        pnl_pct = (pnl / start_value * 100) if start_value > 0 else 0.0

        total_vol = self._total_buy_volume + self._total_sell_volume
        fill_rate = (self._total_fills / max(1, self._cycle)) * 60  # fills/min

        uptime_s = int(time.time() - self._start_time)

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
                "target": round(self.target_price, 2) if self.target_price else None,
                "deviation_pct": round(
                    abs(self._mid - self.target_price) / self.target_price * 100, 3
                ) if self.target_price else None,
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
                "total_fills": self._total_fills,
                "maker_fills": self._maker_fills,
                "organic_fills": self._organic_fills,
                "total_volume": round(total_vol, 6),
                "buy_volume": round(self._total_buy_volume, 6),
                "sell_volume": round(self._total_sell_volume, 6),
                "spread_revenue": round(self._spread_revenue, 4),
                "fill_rate_per_min": round(fill_rate, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 4),
                "portfolio_value": round(curr_value, 2),
                "uptime_s": uptime_s,
                "organic_orders": sum(1 for o in self.open_orders.values() if o.is_organic),
            },
        }
