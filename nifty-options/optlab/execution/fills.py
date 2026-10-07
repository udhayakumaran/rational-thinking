"""Simulated execution. Seeing a price is not the same as getting filled there.

Fill models (per leg, every leg pays its own spread/slippage):
  optimistic   ~ mid
  realistic    mid +/- `realistic_spread_fraction` of the half-spread + slippage ticks
  pessimistic  at the touch (ask for buys, bid for sells) + slippage ticks

When the data has no observed bid/ask (EOD or OHLC-only data), the spread is
*estimated* from price via ``SpreadEstimator`` and the fill is flagged.
Prices are rounded to the tick AGAINST the trader.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from ..core.market import TICK, Quote
from .costs import Side


class FillModelName(str, Enum):
    OPTIMISTIC = "optimistic"
    REALISTIC = "realistic"
    PESSIMISTIC = "pessimistic"


@dataclass(frozen=True)
class SpreadEstimator:
    """Half-spread estimate (points) used only when bid/ask are unobserved."""
    min_half_spread: float = 0.05
    rel_half_spread: float = 0.005   # 0.5% of premium each side
    cheap_price: float = 5.0         # sub-Rs-5 options: very wide relative spreads
    cheap_half_spread: float = 0.10

    def half_spread(self, price: float) -> float:
        if price <= self.cheap_price:
            return max(self.cheap_half_spread, self.min_half_spread)
        return max(self.min_half_spread, self.rel_half_spread * price)


@dataclass(frozen=True)
class Fill:
    price: float
    mid: float
    side: Side
    slippage_points: float     # adverse distance from mid (>= 0 normally)
    spread_estimated: bool


@dataclass
class FillModel:
    name: FillModelName = FillModelName.REALISTIC
    realistic_spread_fraction: float = 0.5
    slippage_ticks: int = 1
    tick: float = TICK
    estimator: SpreadEstimator = field(default_factory=SpreadEstimator)

    def _bid_ask(self, q: Quote) -> tuple[float, float, bool]:
        """Two-sided market, or an LTP-only (EOD/OHLC) quote with an estimated spread."""
        if q.has_two_sided:
            return q.bid, q.ask, q.spread_estimated
        if not (math.isfinite(q.ltp) and q.ltp > 0):
            raise ValueError(f"no usable price for {q.contract.symbol} at {q.ts}")
        h = self.estimator.half_spread(q.ltp)
        return max(q.ltp - h, self.tick), q.ltp + h, True

    @staticmethod
    def _side_present(x: float) -> bool:
        return math.isfinite(x) and x > 0

    def _one_sided(self, q: Quote) -> bool:
        """Exactly one side of the book observed (the other missing or zero)."""
        return self._side_present(q.bid) != self._side_present(q.ask)

    def fill(self, side: Side, q: Quote) -> Fill:
        slip = self.slippage_ticks * self.tick
        if self._one_sided(q):
            # only the observed touch is executable; never price off a stale LTP
            if side is Side.BUY and not self._side_present(q.ask):
                raise ValueError(f"no ask for {q.contract.symbol} at {q.ts}")
            if side is Side.SELL and not self._side_present(q.bid):
                raise ValueError(f"no bid for {q.contract.symbol} at {q.ts}")
            touch = q.ask if side is Side.BUY else q.bid
            raw = touch + slip if side is Side.BUY else touch - slip
            price = max(_round_against(raw, side, self.tick), self.tick)
            mid = self.mid(q)
            return Fill(price=price, mid=mid, side=side,
                        slippage_points=(price - mid) if side is Side.BUY else (mid - price), spread_estimated=True)
        bid, ask, est = self._bid_ask(q)
        mid = 0.5 * (bid + ask)
        half = 0.5 * (ask - bid)
        if self.name is FillModelName.OPTIMISTIC:
            adverse = 0.0
        elif self.name is FillModelName.REALISTIC:
            adverse = self.realistic_spread_fraction * half + slip
        else:
            adverse = half + slip
        raw = mid + adverse if side is Side.BUY else mid - adverse
        price = _round_against(raw, side, self.tick)
        price = max(price, self.tick)
        slippage = (price - mid) if side is Side.BUY else (mid - price)
        return Fill(price=price, mid=mid, side=side, slippage_points=slippage, spread_estimated=est)

    def mid(self, q: Quote) -> float:
        """Mark price. One-sided books are marked conservatively inside the observed side."""
        if self._one_sided(q):
            if self._side_present(q.ask):
                ltp_ok = math.isfinite(q.ltp) and q.ltp > 0
                return min(q.ltp, q.ask) if ltp_ok else 0.5 * q.ask
            return q.bid
        bid, ask, _ = self._bid_ask(q)
        return 0.5 * (bid + ask)

    @classmethod
    def from_config(cls, cfg: dict) -> "FillModel":
        cfg = dict(cfg or {})
        est = SpreadEstimator(**cfg.pop("spread_estimator", {}))
        return cls(name=FillModelName(cfg.pop("name", "realistic")), estimator=est, **cfg)


def _round_against(price: float, side: Side, tick: float) -> float:
    n = price / tick
    n = math.ceil(n - 1e-9) if side is Side.BUY else math.floor(n + 1e-9)
    return round(n * tick, 2)
