"""Monte Carlo resampling of trade sequences.

Trades are resampled as R-multiples (net P&L / planned max risk) and replayed
with fixed-fractional sizing, so results answer: "with Rs X capital risking
p% per trade, what range of outcomes should we expect?". Optional block
bootstrap preserves short-range dependence (losing clusters).

Caveat printed in every report: resampling assumes the future trade
distribution equals the past one. It quantifies luck, not model risk.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class MCResult:
    n_sims: int
    n_trades: int
    final_capital_pcts: dict
    max_dd_pcts: dict
    p_loss_10: float
    p_loss_20: float
    p_dd_20: float
    p_ruin: float
    ruin_level: float
    expected_max_losing_streak: float
    p95_max_losing_streak: float
    median_final: float

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def monte_carlo(r_multiples, initial_capital: float = 100_000.0, risk_pct: float = 0.01, n_trades: int | None = None,
                n_sims: int = 5000, block: int = 1, ruin_drawdown: float = 0.5, seed: int = 0) -> MCResult:
    r = np.asarray(r_multiples, dtype=float)
    r = r[np.isfinite(r)]
    if r.size == 0:
        raise ValueError("no trades")
    n = n_trades or r.size
    rng = np.random.default_rng(seed)
    if block <= 1:
        idx = rng.integers(0, r.size, size=(n_sims, n))
    else:
        nb = int(np.ceil(n / block))
        starts = rng.integers(0, max(r.size - block + 1, 1), size=(n_sims, nb))
        idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(n_sims, -1)[:, :n] % r.size
    seq = r[idx]
    # fixed-fractional: each trade risks risk_pct of current equity; loss capped at -1R by construction
    growth = np.maximum(1 + risk_pct * seq, 0.0)
    eq = initial_capital * np.cumprod(growth, axis=1)
    eq = np.concatenate([np.full((n_sims, 1), initial_capital), eq], axis=1)
    peak = np.maximum.accumulate(eq, axis=1)
    dd = 1 - eq / peak
    max_dd = dd.max(axis=1)
    final = eq[:, -1]
    losing = seq <= 0
    streaks = np.zeros(n_sims)
    cur = np.zeros(n_sims)
    for j in range(n):
        cur = np.where(losing[:, j], cur + 1, 0)
        streaks = np.maximum(streaks, cur)
    q = [5, 25, 50, 75, 95]
    return MCResult(
        n_sims=n_sims, n_trades=n,
        final_capital_pcts={f"p{p}": float(np.percentile(final, p)) for p in q},
        max_dd_pcts={f"p{p}": float(np.percentile(max_dd, p)) for p in q},
        p_loss_10=float(np.mean(final <= 0.9 * initial_capital)),
        p_loss_20=float(np.mean(final <= 0.8 * initial_capital)),
        p_dd_20=float(np.mean(max_dd >= 0.2)),
        p_ruin=float(np.mean(max_dd >= ruin_drawdown)), ruin_level=ruin_drawdown,
        expected_max_losing_streak=float(streaks.mean()), p95_max_losing_streak=float(np.percentile(streaks, 95)),
        median_final=float(np.median(final)),
    )
