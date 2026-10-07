"""Anti-overfitting checks, promotion gate and robustness score.

Thresholds are deliberately conservative defaults and are versioned here.
They MUST be revisited once real data is inspected (see docs/STRATEGY_RESEARCH.md);
any change must be recorded in EXPERIMENTS.md with its rationale, and never
made to rescue a specific strategy.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

GATE_VERSION = "gate-v1"


@dataclass(frozen=True)
class Thresholds:
    min_total_trades: int = 150
    min_oos_trades: int = 60
    reject_below_trades: int = 30
    min_oos_exp_r: float = 0.05
    min_oos_tstat: float = 2.0
    min_oos_profit_factor: float = 1.25
    max_top10_profit_share: float = 0.60
    max_best_year_share: float = 0.60
    min_plateau_same_sign: float = 0.60
    oos_collapse_ratio: float = 0.30        # OOS exp_r must be >= 30% of IS exp_r
    max_portfolio_dd: float = 0.15
    max_mc_p_dd20: float = 0.10
    min_regimes_positive: int = 2
    min_trades_per_regime: int = 20
    max_spread_estimated_share: float = 0.20
    min_budget_feasible_share: float = 0.80


@dataclass
class Check:
    name: str
    status: str        # PASS | FLAG | FAIL | N/A
    value: object
    rule: str


@dataclass
class Verdict:
    verdict: str                       # REJECT | FLAGGED | PROMOTE_TO_PAPER
    checks: list[Check] = field(default_factory=list)
    score: float = math.nan
    gate_version: str = GATE_VERSION

    def to_dict(self) -> dict:
        return {"verdict": self.verdict, "score": self.score, "gate_version": self.gate_version,
                "checks": [asdict(c) for c in self.checks]}

    def table(self) -> pd.DataFrame:
        return pd.DataFrame([asdict(c) for c in self.checks])


def _tstat(r: pd.Series) -> float:
    r = r.dropna()
    n = len(r)
    if n < 3 or r.std(ddof=1) == 0:
        return math.nan
    return float(r.mean() / (r.std(ddof=1) / math.sqrt(n)))


def _pf(p: pd.Series) -> float:
    g, l = p[p > 0].sum(), -p[p <= 0].sum()
    return float(g / l) if l > 0 else math.inf


def evaluate(all_trades: pd.DataFrame, is_trades: pd.DataFrame, oos_trades: pd.DataFrame, *,
             pessimistic_oos_trades: pd.DataFrame | None = None, plateau_same_sign: float | None = None,
             portfolio_max_dd: float | None = None, mc_p_dd20: float | None = None,
             th: Thresholds = Thresholds()) -> Verdict:
    C: list[Check] = []
    n_all, n_oos = len(all_trades), len(oos_trades)

    def add(name, ok, value, rule, fail_hard=True, na=False):
        status = "N/A" if na else ("PASS" if ok else ("FAIL" if fail_hard else "FLAG"))
        C.append(Check(name, status, value, rule))

    add("sample_size_total", n_all >= th.min_total_trades, n_all, f">= {th.min_total_trades}",
        fail_hard=n_all < th.reject_below_trades)
    add("sample_size_oos", n_oos >= th.min_oos_trades, n_oos, f">= {th.min_oos_trades}")
    oos_r = oos_trades["r_multiple"] if n_oos else pd.Series(dtype=float)
    is_r = is_trades["r_multiple"] if len(is_trades) else pd.Series(dtype=float)
    e_oos = float(oos_r.mean()) if n_oos else math.nan
    e_is = float(is_r.mean()) if len(is_r) else math.nan
    add("oos_expectancy_r", n_oos > 0 and e_oos >= th.min_oos_exp_r, round(e_oos, 4), f">= {th.min_oos_exp_r}")
    t = _tstat(oos_r) if n_oos else math.nan
    add("oos_tstat", np.isfinite(t) and t >= th.min_oos_tstat, round(t, 2) if np.isfinite(t) else None,
        f">= {th.min_oos_tstat}", fail_hard=False)
    pf = _pf(oos_trades["net_pnl"]) if n_oos else math.nan
    add("oos_profit_factor", n_oos > 0 and pf >= th.min_oos_profit_factor, round(pf, 3) if np.isfinite(pf) else pf,
        f">= {th.min_oos_profit_factor}")
    if np.isfinite(e_is) and e_is > 0 and np.isfinite(e_oos):
        add("oos_collapse", e_oos >= th.oos_collapse_ratio * e_is, round(e_oos / e_is, 3),
            f"OOS/IS >= {th.oos_collapse_ratio}")
    else:
        add("oos_collapse", False, None, "IS expectancy must be positive", na=not np.isfinite(e_is))
    # concentration
    if n_all:
        pnl = all_trades["net_pnl"].astype(float)
        tot = pnl.sum()
        if tot > 0:
            top = np.sort(pnl.to_numpy())[::-1][: max(1, n_all // 10)].sum() / tot
            add("profit_concentration_top10pct", top <= th.max_top10_profit_share, round(float(top), 3),
                f"<= {th.max_top10_profit_share}", fail_hard=False)
            yr = pnl.groupby(pd.to_datetime(all_trades["entry_ts"]).dt.year).sum()
            share = float(yr.max() / tot) if len(yr) > 1 else 1.0
            add("best_year_share", len(yr) > 1 and share <= th.max_best_year_share, round(share, 3),
                f"<= {th.max_best_year_share} (needs >1 year)", fail_hard=False)
        else:
            add("profit_concentration_top10pct", False, None, "total P&L not positive", na=True)
            add("best_year_share", False, None, "total P&L not positive", na=True)
        # liquidity realism
        if "spread_estimated" in all_trades:
            se = float(all_trades["spread_estimated"].mean())
            add("estimated_spread_share", se <= th.max_spread_estimated_share, round(se, 3),
                f"<= {th.max_spread_estimated_share} (fills on unobserved quotes)", fail_hard=False)
        if "budget_feasible_at_1pct" in all_trades:
            bf = float(all_trades["budget_feasible_at_1pct"].mean())
            add("capital_feasibility", bf >= th.min_budget_feasible_share, round(bf, 3),
                f">= {th.min_budget_feasible_share} of trades fit 1 lot in the per-trade budget", fail_hard=False)
        # regimes
        if "regime" in all_trades:
            g = all_trades.groupby("regime")["r_multiple"].agg(["size", "mean"])
            good = int(((g["size"] >= th.min_trades_per_regime) & (g["mean"] > 0)).sum())
            add("regime_consistency", good >= th.min_regimes_positive, good,
                f">= {th.min_regimes_positive} regimes with >= {th.min_trades_per_regime} trades and E[R] > 0",
                fail_hard=False)
    # costs / fills
    if pessimistic_oos_trades is not None and len(pessimistic_oos_trades):
        ep = float(pessimistic_oos_trades["r_multiple"].mean())
        add("pessimistic_fill_expectancy", ep > 0, round(ep, 4), "> 0 under touch fills + slippage")
    if n_oos and "theoretical_pnl" in oos_trades:
        theo, net = float(oos_trades["theoretical_pnl"].sum()), float(oos_trades["net_pnl"].sum())
        add("edge_survives_costs", not (theo > 0 and net <= 0), {"theoretical": round(theo), "net": round(net)},
            "net > 0 whenever theoretical > 0")
    if plateau_same_sign is not None:
        add("parameter_plateau", plateau_same_sign >= th.min_plateau_same_sign, round(plateau_same_sign, 3),
            f"share of neighbours with positive val+test expectancy >= {th.min_plateau_same_sign}", fail_hard=False)
    if portfolio_max_dd is not None:
        add("portfolio_max_drawdown", portfolio_max_dd <= th.max_portfolio_dd, round(portfolio_max_dd, 4),
            f"<= {th.max_portfolio_dd}")
    if mc_p_dd20 is not None:
        add("mc_p_drawdown_20pct", mc_p_dd20 <= th.max_mc_p_dd20, round(mc_p_dd20, 4), f"<= {th.max_mc_p_dd20}")

    fails = [c for c in C if c.status == "FAIL"]
    flags = [c for c in C if c.status == "FLAG"]
    verdict = "REJECT" if fails else ("FLAGGED" if flags else "PROMOTE_TO_PAPER")
    score = robustness_score(e_oos, t, pf, n_oos, plateau_same_sign, portfolio_max_dd, C)
    return Verdict(verdict, C, score)


def robustness_score(e_oos, tstat, pf, n_oos, plateau, max_dd, checks: list[Check],
                     paper_consistency: float | None = None) -> float:
    """0-100 composite. Not a return ranking: rewards OOS edge *quality*.
    weights: OOS expectancy 20, OOS t-stat 20, PF 10, sample 10, plateau 15,
    drawdown 10, regime consistency 5, paper consistency 10 (0 until paper data)."""
    def clip01(x):
        return float(min(max(x, 0.0), 1.0)) if x is not None and np.isfinite(x) else 0.0
    regime = next((c.value for c in checks if c.name == "regime_consistency"), 0) or 0
    s = (20 * clip01((e_oos or 0) / 0.25) + 20 * clip01((tstat or 0) / 3.0) + 10 * clip01(((pf or 0) - 1) / 1.0)
         + 10 * clip01(n_oos / 200) + 15 * clip01(plateau if plateau is not None else 0)
         + 10 * (clip01(1 - (max_dd or 0) / 0.25) if max_dd is not None else 0)
         + 5 * clip01(regime / 3) + 10 * clip01(paper_consistency if paper_consistency is not None else 0))
    return round(s, 1)
