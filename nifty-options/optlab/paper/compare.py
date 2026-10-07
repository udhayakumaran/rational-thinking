"""Backtest-vs-paper comparison and a paper-consistency score.

Question answered: "Is the paper-trading record a plausible draw from the
backtest's trade distribution?" - not "did paper make money this week?".
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..backtest.metrics import drawdown_stats, trade_metrics


def compare(backtest: pd.DataFrame, paper: pd.DataFrame, n_boot: int = 5000, seed: int = 0) -> dict:
    def stats(t: pd.DataFrame) -> dict:
        if t.empty:
            return {}
        m = trade_metrics(t)
        span_days = max((pd.to_datetime(t.entry_ts).max() - pd.to_datetime(t.entry_ts).min()).days, 1)
        eq = t["net_pnl"].cumsum()
        return {"trades": m["trades"], "win_rate": m["win_rate"], "expectancy_r": m.get("expectancy_r"),
                "avg_winner": m["avg_winner"], "avg_loser": m["avg_loser"],
                "avg_slippage": float(t["slippage_rupees"].mean()), "avg_fees": float(t["fees"].mean()),
                "trades_per_month": len(t) / span_days * 30.4,
                "max_dd_rupees": drawdown_stats(eq.reset_index(drop=True))["max_drawdown"]}

    out = {"backtest": stats(backtest), "paper": stats(paper)}
    if len(paper) and len(backtest):
        rng = np.random.default_rng(seed)
        r = backtest["r_multiple"].to_numpy(dtype=float)
        sims = r[rng.integers(0, len(r), size=(n_boot, len(paper)))].mean(axis=1)
        obs = float(paper["r_multiple"].mean())
        pct = float((sims <= obs).mean())
        out["paper_mean_r_percentile_in_backtest"] = pct
        out["paper_consistency"] = float(1 - 2 * abs(pct - 0.5))   # 1 = centre of distribution, 0 = extreme tail
        bt_slip = backtest["slippage_rupees"].mean() / backtest["account_risk"].mean()
        pp_slip = paper["slippage_rupees"].mean() / paper["account_risk"].mean()
        out["slippage_ratio_paper_vs_backtest"] = float(pp_slip / bt_slip) if bt_slip > 0 else math.nan
        out["warning"] = None if len(paper) >= 30 else "fewer than 30 paper trades: comparison is not yet meaningful"
    return out
