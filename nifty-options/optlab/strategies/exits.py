"""Exit policies, evaluated on mid-marks at each bar.

Thresholds are expressed on P&L (value - entry value) relative to a RISK BASE:
the entry debit for debit structures (so "stop 50%" = lose half the premium) and
the maximum theoretical loss for credit structures. Profit targets use the
structure's maximum profit when it is capped.
Rules are checked in a fixed priority order; the first that fires wins.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime, time


@dataclass(frozen=True)
class ExitConfig:
    stop_loss_pct: float | None = 0.5          # exit when value <= debit * (1 - x)
    target_pct_max_profit: float | None = None  # capped structures: value >= debit + x * max_profit
    target_r_multiple: float | None = None      # value >= debit * (1 + x)
    time_stop_bars: int | None = None
    eod_exit_time: str | None = "15:15"        # None = may hold overnight
    max_hold_days: int = 0                      # 0 = intraday only
    expiry_day_exit_time: str = "15:00"        # always flatten before expiry close
    underlying_invalidation: str | None = None  # "or_mid" | "or_opposite" | "vwap"
    trailing_stop_pct: float | None = None      # give back x of peak open profit (fraction of debit)

    def to_dict(self) -> dict:
        return asdict(self)

    def label(self) -> str:
        parts = []
        if self.stop_loss_pct is not None:
            parts.append(f"SL{self.stop_loss_pct:g}")
        if self.target_pct_max_profit is not None:
            parts.append(f"TPmax{self.target_pct_max_profit:g}")
        if self.target_r_multiple is not None:
            parts.append(f"TP{self.target_r_multiple:g}R")
        if self.time_stop_bars:
            parts.append(f"T{self.time_stop_bars}")
        if self.underlying_invalidation:
            parts.append(f"INV:{self.underlying_invalidation}")
        if self.trailing_stop_pct:
            parts.append(f"TR{self.trailing_stop_pct:g}")
        parts.append("EOD" if self.max_hold_days == 0 else f"H{self.max_hold_days}d")
        return "/".join(parts)


@dataclass
class ExitState:
    entry_debit: float          # points per unit, mid basis at entry
    max_profit: float           # points per unit (inf for uncapped)
    direction_sign: int         # +1 bullish, -1 bearish, 0 neutral
    entry_ts: datetime
    features: dict
    bars_held: int = 0
    peak_value: float = -math.inf
    days_held: int = 0
    max_loss: float = math.nan  # points per unit; risk base for credit structures

    @property
    def risk_base(self) -> float:
        return self.entry_debit if self.entry_debit > 0 else self.max_loss


def check_exit(cfg: ExitConfig, st: ExitState, ts: datetime, value: float, spot: float,
               vwap: float | None, is_expiry_day: bool, is_last_bar: bool) -> str | None:
    """Return an exit reason or None. ``value`` = current mid value of the structure."""
    st.peak_value = max(st.peak_value, value)
    base = st.risk_base
    pnl = value - st.entry_debit
    peak_pnl = st.peak_value - st.entry_debit
    if math.isfinite(base) and base > 0:
        if cfg.stop_loss_pct is not None and pnl <= -cfg.stop_loss_pct * base:
            return "stop_loss"
        if cfg.target_pct_max_profit is not None and math.isfinite(st.max_profit) and \
                pnl >= cfg.target_pct_max_profit * st.max_profit:
            return "target_pct_max_profit"
        if cfg.target_r_multiple is not None and pnl >= cfg.target_r_multiple * base:
            return "target_r_multiple"
        if cfg.trailing_stop_pct is not None and peak_pnl > 0 and \
                pnl <= peak_pnl - cfg.trailing_stop_pct * base:
            return "trailing_stop"
    if cfg.underlying_invalidation and st.direction_sign:
        f, s = st.features, st.direction_sign
        lvl = None
        if cfg.underlying_invalidation == "or_mid" and "or_high" in f:
            lvl = 0.5 * (f["or_high"] + f["or_low"])
        elif cfg.underlying_invalidation == "or_opposite" and "or_high" in f:
            lvl = f["or_low"] if s > 0 else f["or_high"]
        elif cfg.underlying_invalidation == "vwap":
            lvl = vwap
        if lvl is not None and s * (spot - lvl) < 0:
            return "underlying_invalidation"
    if cfg.time_stop_bars is not None and st.bars_held >= cfg.time_stop_bars:
        return "time_stop"
    if is_expiry_day and ts.time() >= time.fromisoformat(cfg.expiry_day_exit_time):
        return "pre_expiry_exit"
    if cfg.max_hold_days == 0:
        if cfg.eod_exit_time and ts.time() >= time.fromisoformat(cfg.eod_exit_time):
            return "eod_exit"
        if is_last_bar:
            return "eod_exit"
    elif st.days_held >= cfg.max_hold_days and (is_last_bar or (cfg.eod_exit_time and ts.time() >= time.fromisoformat(cfg.eod_exit_time))):
        return "max_hold_days"
    return None
