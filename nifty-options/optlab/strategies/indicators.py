"""Causal indicators: the value at row t depends only on rows <= t.
(tests/test_causality.py enforces this by truncation.)"""
from __future__ import annotations

import numpy as np
import pandas as pd


def vwap(bars: pd.DataFrame) -> pd.Series:
    """Session VWAP; falls back to TWAP of typical price if volume is missing."""
    tp = (bars["high"] + bars["low"] + bars["close"]) / 3.0
    vol = bars["volume"].astype(float)
    if vol.isna().all() or (vol.fillna(0) <= 0).all():
        return tp.expanding().mean()
    vol = vol.fillna(0.0)
    return (tp * vol).cumsum() / vol.cumsum().replace(0, np.nan)


def ema(x: pd.Series, span: int) -> pd.Series:
    return x.ewm(span=span, adjust=False).mean()


def rsi(x: pd.Series, n: int = 14) -> pd.Series:
    d = x.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def roc(x: pd.Series, n: int) -> pd.Series:
    return x / x.shift(n) - 1.0


def atr(bars: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = bars["close"].shift(1)
    tr = pd.concat([bars["high"] - bars["low"], (bars["high"] - pc).abs(), (bars["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()
