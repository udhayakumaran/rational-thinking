"""Data-quality checks. Run BEFORE any strategy research on a dataset.

Each check returns an Issue with a severity: ERROR blocks research on the
dataset until resolved; WARN must be acknowledged in the experiment notes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import time

import numpy as np
import pandas as pd

from ..core.calendar import SESSION_CLOSE, SESSION_OPEN, TradingCalendar


@dataclass
class Issue:
    check: str
    severity: str     # ERROR | WARN | INFO
    count: int
    detail: str


def check_underlying(bars: pd.DataFrame, bar_minutes: int) -> list[Issue]:
    out: list[Issue] = []
    if bars.empty:
        return [Issue("underlying_present", "ERROR", 0, "no underlying bars")]
    b = bars.copy()
    b["ts"] = pd.to_datetime(b["ts"])
    dup = int(b["ts"].duplicated().sum())
    out.append(Issue("duplicate_timestamps", "ERROR" if dup else "INFO", dup, "duplicate bar timestamps"))
    t = b["ts"].dt.time
    outside = int(((t <= SESSION_OPEN) | (t > SESSION_CLOSE)).sum())
    out.append(Issue("outside_session", "WARN" if outside else "INFO", outside, "bars outside 09:15-15:30 (bar-end)"))
    bad = int(((b.high < b[["open", "close"]].max(axis=1) - 1e-9) | (b.low > b[["open", "close"]].min(axis=1) + 1e-9)
               | (b.low <= 0)).sum())
    out.append(Issue("ohlc_consistency", "ERROR" if bad else "INFO", bad, "high<max(o,c) or low>min(o,c) or low<=0"))
    expected = int(375 / bar_minutes)
    per_day = b.groupby(b["ts"].dt.date).size()
    short = per_day[per_day < expected * 0.95]
    out.append(Issue("missing_bars", "WARN" if len(short) else "INFO", int(len(short)),
                     f"days with <95% of {expected} bars: {list(map(str, short.index[:5]))}"))
    ret = np.log(b["close"]).diff().abs()
    jumps = int((ret > 0.03).sum())
    out.append(Issue("extreme_bar_returns", "WARN" if jumps else "INFO", jumps, "|bar log-return| > 3% (check splits/errors)"))
    days = sorted(per_day.index)
    gaps = [(a, c) for a, c in zip(days, days[1:]) if (c - a).days > 4]
    out.append(Issue("calendar_gaps", "WARN" if gaps else "INFO", len(gaps), f"gaps > 4 calendar days: {gaps[:5]}"))
    return out


def check_options(opt: pd.DataFrame, spot_by_ts: pd.Series | None = None, strike_step: float = 50.0,
                  calendar: TradingCalendar | None = None, stale_bars: int = 6) -> list[Issue]:
    out: list[Issue] = []
    if opt.empty:
        return [Issue("options_present", "ERROR", 0, "no option quotes")]
    o = opt.copy()
    o["ts"] = pd.to_datetime(o["ts"])
    key = ["ts", "expiry", "strike", "right"]
    dup = int(o.duplicated(key).sum())
    out.append(Issue("duplicate_quotes", "ERROR" if dup else "INFO", dup, "duplicate (ts, expiry, strike, right)"))
    off_grid = int((np.abs(o.strike / strike_step - np.round(o.strike / strike_step)) > 1e-9).sum())
    out.append(Issue("strike_grid", "WARN" if off_grid else "INFO", off_grid, f"strikes not multiple of {strike_step}"))
    bad_right = int((~o["right"].isin(["CE", "PE"])).sum())
    out.append(Issue("option_type", "ERROR" if bad_right else "INFO", bad_right, "right not CE/PE"))
    exp = pd.to_datetime(o["expiry"]).dt.date
    after = int((exp < o["ts"].dt.date).sum())
    out.append(Issue("quote_after_expiry", "ERROR" if after else "INFO", after, "quotes dated after their expiry"))
    if calendar is not None:
        bad_exp = sorted({e for e in exp.unique() if not calendar.is_trading_day(e)})
        out.append(Issue("expiry_on_non_trading_day", "WARN" if bad_exp else "INFO", len(bad_exp), str(bad_exp[:5])))
        wd = sorted({e for e in exp.unique() if e.weekday() != calendar.expiry_weekday(e)
                     and calendar.adjust_for_holiday(e) == e and e.weekday() < 5})
        out.append(Issue("expiry_weekday_unexpected", "INFO", len(wd),
                         f"expiries not on rule weekday (holiday shifts/regime changes?): {wd[:8]}"))
    if {"bid", "ask"} <= set(o.columns):
        has = o.bid.notna() & o.ask.notna()
        crossed = int((has & (o.bid > o.ask)).sum())
        out.append(Issue("crossed_quotes", "ERROR" if crossed else "INFO", crossed, "bid > ask"))
        nonpos = int((has & ((o.bid <= 0) | (o.ask <= 0))).sum())
        out.append(Issue("zero_bid_or_ask", "WARN" if nonpos else "INFO", nonpos, "bid or ask <= 0 (one-sided)"))
        mid = (o.bid + o.ask) / 2
        wide = int((has & (mid > 5) & ((o.ask - o.bid) / mid > 0.2)).sum())
        out.append(Issue("abnormal_spreads", "WARN" if wide else "INFO", wide, "relative spread > 20% for mid > 5"))
        miss = int((~has).sum())
        out.append(Issue("missing_bid_ask", "WARN" if miss else "INFO", miss, "no bid/ask -> fills will use estimated spreads"))
    if "volume" in o:
        zv = float((o.volume.fillna(0) <= 0).mean())
        out.append(Issue("zero_volume_share", "WARN" if zv > 0.3 else "INFO", int(zv * len(o)), f"{zv:.1%} rows zero volume"))
    if "ltp" in o:
        o = o.sort_values(key[1:] + ["ts"])
        same = o.groupby(["expiry", "strike", "right"])["ltp"].transform(lambda s: s.diff().eq(0).astype(int)
                                                                           .groupby((s.diff() != 0).cumsum()).cumsum())
        stale = int((same >= stale_bars).sum())
        out.append(Issue("stale_quotes", "WARN" if stale else "INFO", stale, f"LTP unchanged for >= {stale_bars} bars"))
    if spot_by_ts is not None and "ltp" in o:
        s = o["ts"].map(spot_by_ts)
        intrinsic = np.where(o.right == "CE", np.maximum(s - o.strike, 0), np.maximum(o.strike - s, 0))
        px = ((o.bid + o.ask) / 2).where(o.bid.notna() & o.ask.notna(), o.ltp) if "bid" in o else o.ltp
        viol = int(((px + 0.5 + 0.002 * s) < intrinsic).sum())
        out.append(Issue("below_intrinsic", "WARN" if viol else "INFO", viol,
                         "price below intrinsic by > 0.5 + 0.2% spot (stale/mistimed quote or spot mismatch)"))
    return out


def summarize(issues: list[Issue]) -> tuple[bool, pd.DataFrame]:
    df = pd.DataFrame([asdict(i) for i in issues])
    ok = not (df.severity == "ERROR").any() if len(df) else False
    return ok, df
