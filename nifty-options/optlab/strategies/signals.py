"""Directional signal generators.

A signal generator only says *when* and *which direction*. It knows nothing
about options, sizing or execution. ``compute_day`` must be CAUSAL: the output
at bar t depends only on bars <= t, so the paper engine can call it on the
bars-so-far and take the last row, and the backtester can call it once per day.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import time
from typing import Any

import numpy as np
import pandas as pd

from ..core.instruments import Direction
from .indicators import ema, rsi, roc, vwap
from .regime import DayContext


@dataclass(frozen=True)
class SignalEvent:
    ts: Any
    direction: Direction
    reason: str
    features: dict


@dataclass(frozen=True)
class ORBConfig:
    """15-minute opening-range breakout with optional, individually testable filters."""
    or_minutes: int = 15
    require_vwap: bool = True
    momentum_bars: int = 3
    momentum_min_pct: float = 0.0          # return over momentum_bars must exceed this (in %)
    entry_start: str = "09:30"
    entry_end: str = "14:00"
    allow_long: bool = True
    allow_short: bool = True
    max_signals_per_day: int = 1
    # ---- optional filters (None = off). Add ONE at a time in research.
    vix_max: float | None = None
    vix_min: float | None = None
    max_abs_gap_pct: float | None = None
    min_or_width_pct: float | None = None
    max_or_width_pct: float | None = None
    trend_align: bool = False              # long only in bull trend, short only in bear
    skip_expiry_day: bool = False
    rsi_len: int | None = None             # if set, long needs RSI>rsi_long_min, short RSI<100-rsi_long_min
    rsi_long_min: float = 55.0
    ema_slope_len: int | None = None       # if set, EMA slope must agree with direction

    def to_dict(self) -> dict:
        return asdict(self)


class OpeningRangeBreakout:
    name = "orb"

    def __init__(self, cfg: ORBConfig = ORBConfig(), bar_minutes: int = 5):
        self.cfg = cfg
        self.bar_minutes = bar_minutes

    def compute_day(self, bars: pd.DataFrame, ctx: DayContext | None) -> list[SignalEvent]:
        c = self.cfg
        if bars.empty:
            return []
        n_or = max(1, c.or_minutes // self.bar_minutes)
        if len(bars) <= n_or:
            return []
        # day-level filters (all ex-ante)
        if ctx is not None:
            if c.skip_expiry_day and ctx.is_expiry_day:
                return []
            if c.vix_max is not None and not (ctx.vix_open <= c.vix_max):
                return []
            if c.vix_min is not None and not (ctx.vix_open >= c.vix_min):
                return []
            if c.max_abs_gap_pct is not None and not (abs(ctx.gap_pct) * 100 <= c.max_abs_gap_pct):
                return []
        close = bars["close"].reset_index(drop=True)
        or_hi = float(bars["high"].iloc[:n_or].max())
        or_lo = float(bars["low"].iloc[:n_or].min())
        or_width_pct = (or_hi - or_lo) / or_lo * 100
        if c.min_or_width_pct is not None and or_width_pct < c.min_or_width_pct:
            return []
        if c.max_or_width_pct is not None and or_width_pct > c.max_or_width_pct:
            return []
        vw = vwap(bars).reset_index(drop=True)
        mom = roc(close, c.momentum_bars) * 100
        r = rsi(close, c.rsi_len) if c.rsi_len else None
        e = ema(close, c.ema_slope_len) if c.ema_slope_len else None
        t0, t1 = time.fromisoformat(c.entry_start), time.fromisoformat(c.entry_end)
        out: list[SignalEvent] = []
        for i in range(n_or, len(bars)):
            ts = bars["ts"].iloc[i]
            if not (t0 <= ts.time() <= t1):
                continue
            px = close.iloc[i]
            long_ok = c.allow_long and px > or_hi
            short_ok = c.allow_short and px < or_lo
            if not (long_ok or short_ok):
                continue
            d = Direction.BULLISH if long_ok else Direction.BEARISH
            sgn = 1 if long_ok else -1
            if c.require_vwap and not (sgn * (px - vw.iloc[i]) > 0):
                continue
            m = mom.iloc[i]
            if not (np.isfinite(m) and sgn * m > c.momentum_min_pct):
                continue
            if r is not None:
                rv = r.iloc[i]
                if not (np.isfinite(rv) and (rv > c.rsi_long_min if sgn > 0 else rv < 100 - c.rsi_long_min)):
                    continue
            if e is not None and i >= 1 and not (sgn * (e.iloc[i] - e.iloc[i - 1]) > 0):
                continue
            if c.trend_align and ctx is not None and ctx.trend != ("bull" if sgn > 0 else "bear"):
                continue
            feats = {"or_high": or_hi, "or_low": or_lo, "or_width_pct": or_width_pct, "spot": float(px),
                     "vwap": float(vw.iloc[i]), "mom_pct": float(m), "bar_index": i}
            if ctx is not None:
                feats.update({"vix": ctx.vix_open, "gap_pct": ctx.gap_pct, "regime": ctx.regime,
                              "vol_dynamics": ctx.vol_dynamics, "tags": list(ctx.tags)})
            out.append(SignalEvent(ts, d, f"ORB{c.or_minutes} {'up' if sgn > 0 else 'down'}-break", feats))
            if len(out) >= c.max_signals_per_day:
                break
        return out


SIGNALS = {"orb": (OpeningRangeBreakout, ORBConfig)}


def make_signal(name: str, params: dict, bar_minutes: int):
    cls, cfg_cls = SIGNALS[name]
    return cls(cfg_cls(**(params or {})), bar_minutes=bar_minutes)
