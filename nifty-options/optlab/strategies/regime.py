"""Ex-ante market-regime classification and per-day context.

Every field for day D uses only information available at D's open (prior
daily closes, prior VIX history, today's opening print and opening VIX), so
it can be used both as an entry filter and to slice results by regime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from ..data.interfaces import MarketData


@dataclass(frozen=True)
class DayContext:
    day: date
    prev_close: float
    prev_high: float
    prev_low: float
    open: float
    gap_pct: float
    sma20: float
    sma50: float
    vix_open: float
    vix_pctile: float          # percentile of today's VIX vs trailing 252 prior days
    vix_vs_5d: float           # today's VIX / mean of prior 5 days
    is_expiry_day: bool
    trend: str                 # bull | bear | range | unknown
    vol: str                   # high | low | normal | unknown
    vol_dynamics: str          # expansion | contraction | stable | unknown
    tags: tuple[str, ...] = field(default=())

    @property
    def regime(self) -> str:
        return f"{self.trend}/{self.vol}"


def build_day_contexts(md: MarketData, gap_threshold: float = 0.005) -> dict[date, DayContext]:
    days = md.trading_days()
    rows = []
    for d in days:
        b = md.underlying_bars(d)
        if not len(b):
            continue
        v = md.vix(d)
        rows.append({"date": d, "open": float(b.open.iloc[0]), "high": float(b.high.max()),
                     "low": float(b.low.min()), "close": float(b.close.iloc[-1]),
                     "vix": float(v.iloc[0]) if len(v) else np.nan})
    df = pd.DataFrame(rows).set_index("date")
    prev = df.shift(1)
    sma20 = df.close.rolling(20).mean().shift(1)
    sma50 = df.close.rolling(50).mean().shift(1)
    vix_hist = df.vix.shift(1)
    vix_pct = [
        float((vix_hist.iloc[max(0, i - 252):i].dropna() < df.vix.iloc[i]).mean()) if i >= 60 else np.nan
        for i in range(len(df))
    ]
    vix5 = vix_hist.rolling(5).mean()
    out: dict[date, DayContext] = {}
    for i, d in enumerate(df.index):
        pc = prev.close.iloc[i]
        gap = df.open.iloc[i] / pc - 1 if pd.notna(pc) else np.nan
        s20, s50 = sma20.iloc[i], sma50.iloc[i]
        if pd.isna(s50):
            trend = "unknown"
        elif pc > s20 > s50:
            trend = "bull"
        elif pc < s20 < s50:
            trend = "bear"
        else:
            trend = "range"
        vp = vix_pct[i]
        vol = "unknown" if np.isnan(vp) else ("high" if vp >= 0.7 else "low" if vp <= 0.3 else "normal")
        ratio = df.vix.iloc[i] / vix5.iloc[i] if pd.notna(vix5.iloc[i]) else np.nan
        dyn = "unknown" if np.isnan(ratio) else ("expansion" if ratio > 1.1 else "contraction" if ratio < 0.9 else "stable")
        is_exp = d in set(md.expiries(d)[:1])
        tags = []
        if pd.notna(gap) and abs(gap) >= gap_threshold:
            tags.append("gap_day")
        if is_exp:
            tags.append("expiry_day")
        out[d] = DayContext(d, pc, prev.high.iloc[i], prev.low.iloc[i], df.open.iloc[i], gap, s20, s50,
                            df.vix.iloc[i], vp, ratio, is_exp, trend, vol, dyn, tuple(tags))
    return out
