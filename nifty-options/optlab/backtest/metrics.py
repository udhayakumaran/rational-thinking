"""Performance metrics. Expectancy (in rupees AND in R) is the headline number."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _streaks(wins: np.ndarray) -> tuple[int, int]:
    best_w = best_l = cur_w = cur_l = 0
    for w in wins:
        if w:
            cur_w += 1; cur_l = 0
        else:
            cur_l += 1; cur_w = 0
        best_w, best_l = max(best_w, cur_w), max(best_l, cur_l)
    return best_w, best_l


def drawdown_stats(equity: pd.Series) -> dict:
    if equity.empty:
        return {"max_drawdown": 0.0, "max_drawdown_pct": 0.0, "avg_drawdown_pct": 0.0, "max_dd_duration": 0}
    peak = equity.cummax()
    dd = equity - peak
    dd_pct = dd / peak
    under = (dd < 0).astype(int).to_numpy()
    longest = cur = 0
    for u in under:
        cur = cur + 1 if u else 0
        longest = max(longest, cur)
    neg = dd_pct[dd_pct < 0]
    return {"max_drawdown": float(-dd.min()), "max_drawdown_pct": float(-dd_pct.min()),
            "avg_drawdown_pct": float(-neg.mean()) if len(neg) else 0.0, "max_dd_duration": int(longest)}


def trade_metrics(trades: pd.DataFrame, pnl_col: str = "net_pnl") -> dict:
    n = len(trades)
    if n == 0:
        return {"trades": 0}
    pnl = trades[pnl_col].astype(float).to_numpy()
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    p_win = len(wins) / n
    avg_w = float(wins.mean()) if len(wins) else 0.0
    avg_l = float(-losses.mean()) if len(losses) else 0.0
    gross_w, gross_l = float(wins.sum()), float(-losses.sum())
    cw, cl = _streaks(pnl > 0)
    out = {
        "trades": n, "wins": int(len(wins)), "losses": int(len(losses)), "win_rate": p_win,
        "avg_winner": avg_w, "avg_loser": avg_l,
        "payoff_ratio": avg_w / avg_l if avg_l > 0 else math.inf,
        "expectancy": p_win * avg_w - (1 - p_win) * avg_l,
        "expectancy_check_mean": float(pnl.mean()),
        "profit_factor": gross_w / gross_l if gross_l > 0 else math.inf,
        "total_pnl": float(pnl.sum()), "largest_win": float(pnl.max()), "largest_loss": float(pnl.min()),
        "max_consec_wins": cw, "max_consec_losses": cl,
        "pnl_std": float(pnl.std(ddof=1)) if n > 1 else math.nan,
    }
    if n > 1 and out["pnl_std"] > 0:
        out["expectancy_tstat"] = float(pnl.mean() / (out["pnl_std"] / math.sqrt(n)))
    if "r_multiple" in trades:
        r = trades["r_multiple"].astype(float).to_numpy()
        out.update({"expectancy_r": float(np.nanmean(r)), "median_r": float(np.nanmedian(r)),
                    "r_std": float(np.nanstd(r, ddof=1)) if n > 1 else math.nan})
    if "holding_minutes" in trades:
        h = trades["holding_minutes"].astype(float)
        out.update({"avg_holding_min": float(h.mean()), "median_holding_min": float(h.median())})
    for col in ("fees", "slippage_rupees", "theoretical_pnl", "gross_pnl"):
        if col in trades:
            out[f"total_{col}"] = float(trades[col].sum())
    # concentration: share of total profit from the top 10% of trades
    if out["total_pnl"] > 0:
        top = np.sort(pnl)[::-1][: max(1, n // 10)]
        out["top10pct_profit_share"] = float(top.sum() / out["total_pnl"])
    return out


def equity_metrics(daily: pd.DataFrame, initial_capital: float) -> dict:
    if daily.empty:
        return {}
    eq = daily.set_index("date")["equity"].astype(float)
    eq_full = pd.concat([pd.Series([initial_capital]), eq.reset_index(drop=True)])
    rets = eq_full.pct_change().dropna()
    years = max(len(eq) / TRADING_DAYS, 1e-9)
    final = float(eq.iloc[-1])
    total_ret = final / initial_capital - 1
    cagr = (final / initial_capital) ** (1 / years) - 1 if final > 0 else -1.0
    sd = rets.std(ddof=1)
    downside = rets[rets < 0]
    dsd = math.sqrt((downside ** 2).sum() / max(len(rets), 1))
    dd = drawdown_stats(eq_full.reset_index(drop=True))
    return {
        "final_equity": final, "total_return": total_ret, "cagr": cagr,
        "annualized_return": float(rets.mean() * TRADING_DAYS),
        "sharpe": float(rets.mean() / sd * math.sqrt(TRADING_DAYS)) if sd > 0 else math.nan,
        "sortino": float(rets.mean() / dsd * math.sqrt(TRADING_DAYS)) if dsd > 0 else math.nan,
        "calmar": cagr / dd["max_drawdown_pct"] if dd["max_drawdown_pct"] > 0 else math.nan,
        **dd, "days": len(eq),
    }


def full_metrics(result, pnl_col: str = "net_pnl") -> dict:
    m = trade_metrics(result.trades, pnl_col)
    m.update(equity_metrics(result.daily, result.meta.get("initial_capital", 100_000.0)))
    if len(result.trades):
        days = max(result.meta.get("n_days", 1), 1)
        m["trades_per_month"] = len(result.trades) / days * 21
        if "budget_feasible_at_1pct" in result.trades:
            m["share_budget_feasible_1pct"] = float(result.trades["budget_feasible_at_1pct"].mean())
    m["signals"] = len(result.signals)
    m["rejections"] = len(result.rejections)
    return m


def by_group(trades: pd.DataFrame, col: str, pnl_col: str = "r_multiple") -> pd.DataFrame:
    if trades.empty or col not in trades:
        return pd.DataFrame()
    g = trades.groupby(col)[pnl_col]
    return pd.DataFrame({"trades": g.size(), "mean": g.mean(), "win_rate": g.apply(lambda x: (x > 0).mean()),
                         "total": g.sum()})
