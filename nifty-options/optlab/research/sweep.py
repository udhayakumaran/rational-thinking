"""Parameter grids, sensitivity tables and plateau (stability) scoring.

Each grid point is backtested once over the FULL period; train/validation/
test and walk-forward analyses then slice the resulting trade lists by date.
This is valid because research-mode backtests trade one lot and keep no
cross-trade state that depends on earlier P&L.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from ..backtest.engine import Backtester, BacktestResult
from ..strategies.base import Strategy, StrategyConfig
from .splits import Window, slice_trades


def set_path(cfg: StrategyConfig, path: str, value) -> StrategyConfig:
    """Return a copy of cfg with a dotted path replaced, e.g. 'exits.stop_loss_pct'."""
    head, _, tail = path.partition(".")
    if head == "signal_params":
        p = dict(cfg.signal_params)
        p[tail] = value
        return replace(cfg, signal_params=p)
    if head in ("structure", "exits", "liquidity"):
        return replace(cfg, **{head: replace(getattr(cfg, head), **{tail: value})})
    raise KeyError(path)


@dataclass
class GridResult:
    grid: dict[str, list]
    points: list[tuple]                 # tuples of values in grid-key order
    results: dict[tuple, BacktestResult]

    def table(self, window: Window | None = None, col: str = "r_multiple", min_trades: int = 1) -> pd.DataFrame:
        rows = []
        for pt in self.points:
            t = self.results[pt].trades
            if window is not None:
                t = slice_trades(t, window)
            n = len(t)
            r = t[col].astype(float) if n else pd.Series(dtype=float)
            pos, neg = (t["net_pnl"][t["net_pnl"] > 0].sum(), -t["net_pnl"][t["net_pnl"] <= 0].sum()) if n else (0, 0)
            rows.append({**dict(zip(self.grid, pt)), "trades": n,
                         "exp_r": float(r.mean()) if n >= min_trades else math.nan,
                         "tstat": float(r.mean() / (r.std(ddof=1) / math.sqrt(n))) if n > 2 and r.std(ddof=1) > 0 else math.nan,
                         "win_rate": float((r > 0).mean()) if n else math.nan,
                         "profit_factor": float(pos / neg) if neg > 0 else math.nan,
                         "net_pnl": float(t["net_pnl"].sum()) if n else 0.0})
        return pd.DataFrame(rows)


def run_grid(bt: Backtester, base: StrategyConfig, grid: dict[str, list], progress=None) -> GridResult:
    keys = list(grid)
    points = list(itertools.product(*(grid[k] for k in keys)))
    results = {}
    for j, pt in enumerate(points):
        cfg = base
        for k, v in zip(keys, pt):
            cfg = set_path(cfg, k, v)
        results[pt] = bt.run(Strategy(cfg, bt.md))
        if progress:
            progress(j + 1, len(points), pt)
    return GridResult(grid, points, results)


def neighbours(point: tuple, grid: dict[str, list]) -> list[tuple]:
    keys = list(grid)
    out = []
    for d, k in enumerate(keys):
        vals = grid[k]
        i = vals.index(point[d])
        for j in (i - 1, i + 1):
            if 0 <= j < len(vals):
                p = list(point); p[d] = vals[j]; out.append(tuple(p))
    return out


def plateau_scores(gr: GridResult, window: Window | None = None, metric: str = "exp_r") -> pd.DataFrame:
    """For each point: neighbourhood mean, share of neighbours that are also POSITIVE
    (0 when the point itself is not positive - a plateau of losers is not robustness),
    and a 'robust value' = min(point, neighbourhood mean). Isolated peaks score low."""
    tab = gr.table(window)
    keys = list(gr.grid)
    val = {tuple(r[k] for k in keys): r[metric] for _, r in tab.iterrows()}
    rows = []
    for pt in gr.points:
        v = val[pt]
        nb = [val[n] for n in neighbours(pt, gr.grid) if np.isfinite(val[n])]
        nb_mean = float(np.mean(nb)) if nb else math.nan
        if not (nb and np.isfinite(v)):
            same = math.nan
        else:
            same = float(np.mean([x > 0 for x in nb])) if v > 0 else 0.0
        rows.append({**dict(zip(keys, pt)), metric: v, "nb_mean": nb_mean, "nb_same_sign": same,
                     "robust_value": min(v, nb_mean) if np.isfinite(v) and np.isfinite(nb_mean) else math.nan})
    return pd.DataFrame(rows)


def select_robust(gr: GridResult, window: Window, min_trades: int = 20) -> tuple:
    """Choose the parameter point with the best *neighbourhood-robust* value
    (not the raw peak) on ``window``."""
    ps = plateau_scores(gr, window)
    tab = gr.table(window)
    ps["trades"] = tab["trades"].to_numpy()
    ok = ps[(ps.trades >= min_trades) & ps.robust_value.notna()]
    if ok.empty:
        return gr.points[0]
    best = ok.sort_values("robust_value", ascending=False).iloc[0]
    return tuple(best[k] for k in gr.grid)
