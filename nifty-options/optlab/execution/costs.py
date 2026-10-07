"""Indian exchange-traded index-option transaction costs (NSE).

All rates are configurable (see config/default.yaml -> costs). Defaults
reflect a flat-fee discount broker and NSE charges as understood at the time
of writing; rates marked VERIFY must be re-checked against the latest NSE /
SEBI / Finance Act notifications before trusting absolute rupee figures.

Per executed order (one leg, one side):
  brokerage       flat per order
  exchange txn    % of premium turnover
  SEBI fee        % of premium turnover (Rs 10 / crore)
  stamp duty      % of premium turnover, BUY side only
  STT             % of premium turnover, SELL side only
  GST             % of (brokerage + exchange txn + SEBI fee)
At expiry, long ITM options are exercised: STT on intrinsic value (exercise rate).
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class SttRate:
    effective_from: date
    sell_premium_pct: float
    exercise_intrinsic_pct: float


# Sources checked by independent review (2026-10): Finance Acts 2016/2023/2024/2026.
DEFAULT_STT_SCHEDULE = (
    SttRate(date(2000, 1, 1), 0.00017, 0.00125),    # pre-2016 exercise STT was on settlement value (approx.)
    SttRate(date(2016, 6, 1), 0.0005, 0.00125),
    SttRate(date(2023, 4, 1), 0.000625, 0.00125),   # Finance Act 2023
    SttRate(date(2024, 10, 1), 0.001, 0.00125),     # Finance Act 2024
    SttRate(date(2026, 4, 1), 0.0015, 0.0015),      # Union Budget 2026
)

# NSE options transaction charge (% of premium). Pre-Oct-2024 values: medium confidence.
DEFAULT_EXCHANGE_SCHEDULE = (
    (date(2000, 1, 1), 0.00053),      # VERIFY exact history
    (date(2023, 1, 1), 0.000495),     # VERIFY effective date
    (date(2024, 10, 1), 0.0003503),   # flat rate from 2024-10-01 (confirmed)
)


@dataclass(frozen=True)
class CostBreakdown:
    brokerage: float = 0.0
    exchange: float = 0.0
    sebi: float = 0.0
    stamp: float = 0.0
    stt: float = 0.0
    gst: float = 0.0

    @property
    def total(self) -> float:
        return self.brokerage + self.exchange + self.sebi + self.stamp + self.stt + self.gst

    def __add__(self, other: "CostBreakdown") -> "CostBreakdown":
        return CostBreakdown(*(getattr(self, f) + getattr(other, f) for f in
                               ("brokerage", "exchange", "sebi", "stamp", "stt", "gst")))


@dataclass
class CostModel:
    brokerage_per_order: float = 20.0
    exchange_txn_pct: float | None = None  # if set, overrides the dated schedule (flat rate)
    exchange_schedule: tuple = field(default=DEFAULT_EXCHANGE_SCHEDULE)
    sebi_pct: float = 0.000001            # Rs 10 per crore
    stamp_buy_pct: float = 0.00003
    gst_pct: float = 0.18
    stt_schedule: tuple[SttRate, ...] = field(default=DEFAULT_STT_SCHEDULE)
    exercise_brokerage: float = 0.0       # some brokers charge on auto-exercise

    def stt_rate(self, d: date) -> SttRate:
        idx = bisect.bisect_right([s.effective_from for s in self.stt_schedule], d) - 1
        return self.stt_schedule[max(idx, 0)]

    def exchange_rate(self, d: date) -> float:
        if self.exchange_txn_pct is not None:
            return self.exchange_txn_pct
        idx = bisect.bisect_right([s[0] for s in self.exchange_schedule], d) - 1
        return self.exchange_schedule[max(idx, 0)][1]

    def order_costs(self, side: Side, price: float, units: int, trade_date: date) -> CostBreakdown:
        """Costs for one executed order of ``units`` (= lots * lot_size) at ``price``."""
        if units <= 0:
            return CostBreakdown()
        turnover = price * units
        brokerage = self.brokerage_per_order
        exchange = turnover * self.exchange_rate(trade_date)
        sebi = turnover * self.sebi_pct
        stamp = turnover * self.stamp_buy_pct if side is Side.BUY else 0.0
        stt = turnover * self.stt_rate(trade_date).sell_premium_pct if side is Side.SELL else 0.0
        gst = (brokerage + exchange + sebi) * self.gst_pct
        return CostBreakdown(brokerage, exchange, sebi, stamp, stt, gst)

    def exercise_costs(self, intrinsic: float, units: int, expiry: date) -> CostBreakdown:
        """Costs when a LONG ITM option is exercised at expiry."""
        if units <= 0 or intrinsic <= 0:
            return CostBreakdown()
        stt = intrinsic * units * self.stt_rate(expiry).exercise_intrinsic_pct
        gst = self.exercise_brokerage * self.gst_pct
        return CostBreakdown(brokerage=self.exercise_brokerage, stt=stt, gst=gst)

    @classmethod
    def from_config(cls, cfg: dict) -> "CostModel":
        cfg = dict(cfg or {})
        sched = cfg.pop("stt_schedule", None)
        ex = cfg.pop("exchange_schedule", None)
        model = cls(**cfg)
        if ex:
            model.exchange_schedule = tuple((date.fromisoformat(str(e["effective_from"])), float(e["pct"])) for e in ex)
        if sched:
            model.stt_schedule = tuple(
                SttRate(date.fromisoformat(str(s["effective_from"])), float(s["sell_premium_pct"]),
                        float(s["exercise_intrinsic_pct"])) for s in sched)
        return model


ZERO_COSTS = CostModel(brokerage_per_order=0, exchange_txn_pct=0.0, sebi_pct=0, stamp_buy_pct=0, gst_pct=0,
                       stt_schedule=(SttRate(date(2000, 1, 1), 0.0, 0.0),))
