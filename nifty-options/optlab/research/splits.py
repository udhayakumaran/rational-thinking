"""Chronological splits and walk-forward windows. Never shuffle time series."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass(frozen=True)
class Window:
    name: str
    start: date
    end: date

    def mask(self, dates: pd.Series) -> pd.Series:
        d = pd.to_datetime(dates).dt.date
        return (d >= self.start) & (d <= self.end)


def chronological_split(days: list[date], fractions=(0.6, 0.2, 0.2),
                        names=("train", "validation", "test")) -> list[Window]:
    if abs(sum(fractions) - 1) > 1e-9:
        raise ValueError("fractions must sum to 1")
    days = sorted(days)
    n = len(days)
    out, i0 = [], 0
    for k, (f, nm) in enumerate(zip(fractions, names)):
        i1 = n if k == len(fractions) - 1 else i0 + int(round(f * n))
        if i1 <= i0:
            raise ValueError("split too small")
        out.append(Window(nm, days[i0], days[i1 - 1]))
        i0 = i1
    return out


@dataclass(frozen=True)
class WFWindow:
    k: int
    train: Window
    test: Window


def walk_forward_windows(days: list[date], train_days: int, test_days: int, step_days: int | None = None,
                         anchored: bool = False) -> list[WFWindow]:
    """Rolling (or anchored/expanding) train -> test windows over trading days."""
    days = sorted(days)
    step = step_days or test_days
    out, k, start = [], 0, 0
    while start + train_days + test_days <= len(days):
        tr0 = 0 if anchored else start
        tr1 = start + train_days - 1
        te0, te1 = tr1 + 1, tr1 + test_days
        out.append(WFWindow(k, Window(f"train{k}", days[tr0], days[tr1]), Window(f"test{k}", days[te0], days[te1])))
        k += 1
        start += step
    return out


def slice_trades(trades: pd.DataFrame, w: Window, date_col: str = "entry_ts",
                 exit_within: bool = False) -> pd.DataFrame:
    """Trades entered inside ``w``. With ``exit_within`` also require the exit inside ``w``
    (used when CHOOSING parameters so no P&L realised after the window leaks in)."""
    if trades.empty:
        return trades
    m = w.mask(trades[date_col])
    if exit_within and "exit_ts" in trades:
        m &= pd.to_datetime(trades["exit_ts"]).dt.date <= w.end
    return trades[m]
