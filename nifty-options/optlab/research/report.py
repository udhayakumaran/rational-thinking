"""Markdown experiment reports."""
from __future__ import annotations

import math

import pandas as pd


def _f(x, nd=3):
    if x is None:
        return "-"
    if isinstance(x, str):
        return x
    try:
        if math.isnan(x):
            return "-"
        if math.isinf(x):
            return "inf"
    except TypeError:
        return str(x)
    return f"{x:,.{nd}f}" if isinstance(x, float) else f"{x:,}"


def _table(rows: list[dict], cols: list[str] | None = None) -> str:
    if not rows:
        return "_none_\n"
    df = pd.DataFrame(rows)
    cols = cols or list(df.columns)
    head = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    body = "".join("| " + " | ".join(_f(r.get(c)) for c in cols) + " |\n" for r in df.to_dict("records"))
    return head + body


def experiment_markdown(spec: dict, s: dict) -> str:
    L = [f"# {s['experiment_id']} - {spec['title']}\n"]
    if s["is_synthetic"]:
        L.append("> **SYNTHETIC DATA - PIPELINE VALIDATION ONLY.** These numbers say nothing about the real NIFTY "
                 "market and must not be compared with real-data experiments.\n")
    L.append(f"**Hypothesis.** {spec['hypothesis']}\n")
    L.append(f"**Data version:** `{s['data_version']}`  |  **Walk-forward windows:** {s['n_wf_windows']}  |  "
             f"**Runtime:** {s['elapsed_s']}s\n")
    L.append("**Splits:** " + ", ".join(f"{w['name']} {w['start']}..{w['end']}" for w in s["split"]) + "\n")
    L.append("## Variant comparison (identical signals, different option expression)\n")
    rows = []
    for name, v in s["variants"].items():
        oos, full, ex, port = v["walk_forward_oos"], v["full"], v["expression"], v["portfolio"]
        rows.append({"variant": name, "verdict": v["verdict"]["verdict"], "score": v["verdict"]["score"],
                     "trades": full.get("trades"), "OOS trades": oos.get("trades"),
                     "OOS E[R]": oos.get("expectancy_r"), "OOS t": oos.get("expectancy_tstat"),
                     "OOS PF": oos.get("profit_factor"), "win%": full.get("win_rate"),
                     "avg win": full.get("avg_winner"), "avg loss": full.get("avg_loser"),
                     "E[Rs]/lot": full.get("expectancy"), "risk/lot": ex.get("avg_risk_per_lot"),
                     "theta Rs/day": ex.get("avg_entry_theta_rupees_per_day"),
                     "costs in R": ex.get("slippage_plus_fees_in_r"), "theo E[R]": ex.get("theoretical_exp_r"),
                     "fits 1% budget": ex.get("share_budget_feasible_1pct"),
                     "1L port trades": port.get("trades", 0), "1L port maxDD": port.get("max_drawdown_pct"),
                     "1L share taken": v.get("portfolio_trade_share")})
    L.append(_table(rows))
    L.append("\n_E[R] = mean net P&L / planned max risk per trade (1 lot, realistic fills, all costs). "
             "'theo E[R]' = mid-to-mid with no costs. 'fits 1% budget' = share of trades where one lot's max loss "
             "<= 1% of Rs 1L._\n")
    for name, v in s["variants"].items():
        L.append(f"\n## Variant `{name}`\n")
        L.append(f"`{v['label']}`  config `{v['config_hash']}`  chosen params: `{v['chosen_params']}`\n")
        L.append("### Gate checks\n")
        L.append(_table(v["verdict"]["checks"], ["name", "status", "value", "rule"]))
        L.append("\n### Train / validation / test / walk-forward OOS\n")
        keys = ["trades", "win_rate", "expectancy", "expectancy_r", "expectancy_tstat", "profit_factor", "avg_winner",
                "avg_loser", "payoff_ratio", "max_consec_losses"]
        L.append(_table([{"period": p, **{k: v[p].get(k) for k in keys}} for p in
                         ("train", "validation", "test", "walk_forward_oos")], ["period"] + keys))
        L.append("\n### Fill-model stress (test window)\n")
        L.append(_table([{"fill": k, **{kk: m.get(kk) for kk in ("trades", "expectancy_r", "profit_factor", "total_pnl")}}
                         for k, m in v["fills"].items()]))
        L.append("\n### Rs 1,00,000 portfolio simulation (risk limits enforced)\n")
        pm = v["portfolio"]
        L.append(_table([{k: pm.get(k) for k in ("trades", "total_return", "cagr", "max_drawdown_pct", "sharpe",
                                                 "sortino", "calmar", "max_dd_duration")}]))
        L.append(f"\nRejections by stage: `{v['portfolio_rejections']}`; top reasons: `{v['portfolio_rejection_reasons']}`\n")
        if v["monte_carlo"]:
            mc = v["monte_carlo"]
            L.append("\n### Monte Carlo (block bootstrap of OOS trades, discrete lots at the configured risk %, 1-year horizon)\n")
            L.append(f"Share of resampled trades that fit at least one lot: {mc.get('share_trades_taken', float('nan')):.1%}\n")
            L.append(_table([{"sims": mc["n_sims"], "trades/path": mc["n_trades"], "median final": mc["median_final"],
                              "p5 final": mc["final_capital_pcts"]["p5"], "p95 maxDD": mc["max_dd_pcts"]["p95"],
                              "P(-10%)": mc["p_loss_10"], "P(-20%)": mc["p_loss_20"], "P(DD>=20%)": mc["p_dd_20"],
                              f"P(DD>={mc['ruin_level']:.0%})": mc["p_ruin"],
                              "E[max losing streak]": mc["expected_max_losing_streak"]}]))
            mf = v.get("monte_carlo_fractional")
            if mf:
                L.append(f"\nReference only - with divisible lots: median final {mf['median_final']:,.0f}, "
                         f"P(DD>=20%) {mf['p_dd_20']:.3f}.\n")
            L.append("\n_Monte Carlo assumes future trades resemble past ones; it measures luck, not model risk._\n")
        L.append("\n### By regime / volatility / direction / year\n")
        for key in ("by_regime", "by_vol_regime", "by_direction", "by_year", "by_exit_reason"):
            L.append(f"\n**{key}**\n\n" + _table(v[key]))
        if v["walk_forward_windows"]:
            L.append("\n### Walk-forward windows\n")
            L.append(_table(v["walk_forward_windows"], ["k", "train", "test", "params", "is_trades", "is_exp_r",
                                                         "oos_trades", "oos_exp_r"]))
        if v["sensitivity_valtest"]:
            L.append("\n### Parameter sensitivity (validation+test period)\n")
            L.append(_table(v["sensitivity_valtest"]))
    return "\n".join(L)
