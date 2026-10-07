"""Position sizing and portfolio risk limits.

Sizing is driven by the MAXIMUM THEORETICAL LOSS of the complete structure
(plus estimated round-trip costs), never by margin and never by a stop-loss
level (stops can gap). If one lot exceeds the per-trade risk budget the trade
is REJECTED - it is not rounded up to one lot.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date


@dataclass
class RiskLimits:
    initial_capital: float = 100_000.0
    risk_per_trade_pct: float = 0.01
    max_open_risk_pct: float = 0.05
    max_daily_loss_pct: float = 0.03
    max_weekly_loss_pct: float = 0.06
    max_lots_per_trade: int = 10
    max_concurrent_positions: int = 3

    @classmethod
    def from_config(cls, cfg: dict) -> "RiskLimits":
        return cls(**(cfg or {}))


@dataclass(frozen=True)
class SizingDecision:
    lots: int
    risk_per_lot: float          # rupees incl. estimated costs
    total_risk: float
    budget: float
    approved: bool
    reasons: tuple[str, ...] = ()


@dataclass
class RiskManager:
    limits: RiskLimits = field(default_factory=RiskLimits)
    equity: float = math.nan            # realized equity (cash basis)
    open_risk: float = 0.0
    open_positions: int = 0
    _day: date | None = None
    _week: tuple[int, int] | None = None
    day_start_equity: float = math.nan
    week_start_equity: float = math.nan
    realized_today: float = 0.0
    realized_week: float = 0.0
    halted_reason: str | None = None

    def __post_init__(self) -> None:
        if math.isnan(self.equity):
            self.equity = self.limits.initial_capital
        self.day_start_equity = self.week_start_equity = self.equity

    # -- calendar ----------------------------------------------------------
    def on_new_day(self, d: date) -> None:
        if self._day == d:
            return
        wk = d.isocalendar()[:2]
        if self._week != wk:
            self._week = wk
            self.week_start_equity = self.equity
            self.realized_week = 0.0
        self._day = d
        self.day_start_equity = self.equity
        self.realized_today = 0.0
        self.halted_reason = None
        self._update_halt()

    # -- sizing ------------------------------------------------------------
    def trade_budget(self) -> float:
        return self.equity * self.limits.risk_per_trade_pct

    def size(self, max_loss_per_lot: float) -> SizingDecision:
        budget = self.trade_budget()
        reasons: list[str] = []
        if not math.isfinite(max_loss_per_lot) or max_loss_per_lot <= 0:
            return SizingDecision(0, max_loss_per_lot, 0.0, budget, False, ("undefined_or_invalid_max_loss",))
        lots = min(int(budget // max_loss_per_lot), self.limits.max_lots_per_trade)
        if lots < 1:
            reasons.append(f"one_lot_risk_{max_loss_per_lot:.0f}_exceeds_budget_{budget:.0f}")
            return SizingDecision(0, max_loss_per_lot, 0.0, budget, False, tuple(reasons))
        # shrink to fit the open-risk ceiling
        headroom = self.equity * self.limits.max_open_risk_pct - self.open_risk
        lots = min(lots, int(max(headroom, 0) // max_loss_per_lot))
        if lots < 1:
            return SizingDecision(0, max_loss_per_lot, 0.0, budget, False, ("max_open_risk_reached",))
        return SizingDecision(lots, max_loss_per_lot, lots * max_loss_per_lot, budget, True)

    def can_open(self) -> tuple[bool, str | None]:
        self._update_halt()
        if self.halted_reason:
            return False, self.halted_reason
        if self.open_positions >= self.limits.max_concurrent_positions:
            return False, "max_concurrent_positions"
        return True, None

    def check(self, max_loss_per_lot: float) -> SizingDecision:
        ok, why = self.can_open()
        if not ok:
            return SizingDecision(0, max_loss_per_lot, 0.0, self.trade_budget(), False, (why,))
        return self.size(max_loss_per_lot)

    # -- position lifecycle -----------------------------------------------
    def on_open(self, risk: float) -> None:
        self.open_risk += risk
        self.open_positions += 1

    def on_close(self, risk: float, realized_pnl: float) -> None:
        self.open_risk = max(self.open_risk - risk, 0.0)
        self.open_positions = max(self.open_positions - 1, 0)
        self.equity += realized_pnl
        self.realized_today += realized_pnl
        self.realized_week += realized_pnl
        self._update_halt()

    def _update_halt(self) -> None:
        if self.realized_today <= -self.limits.max_daily_loss_pct * self.day_start_equity:
            self.halted_reason = "daily_loss_limit"
        elif self.realized_week <= -self.limits.max_weekly_loss_pct * self.week_start_equity:
            self.halted_reason = "weekly_loss_limit"
        elif self.equity <= 0:
            self.halted_reason = "account_ruined"
