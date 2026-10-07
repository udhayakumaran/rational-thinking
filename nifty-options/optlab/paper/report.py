"""End-of-day paper-trading report. Observational only: nothing in here
changes any strategy. Strategy changes require a new experiment."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from ..backtest.metrics import trade_metrics


def daily_report(engine, d: date) -> Path:
    md = engine.md
    bars = md.underlying_bars(d)
    ctx = engine.contexts().get(d)
    trades = engine.trades_df()
    today = trades[pd.to_datetime(trades["exit_ts"]).dt.date == d] if len(trades) else trades
    entered = trades[pd.to_datetime(trades["entry_ts"]).dt.date == d] if len(trades) else trades
    sigs = [s for c in engine.cores for s in c.signals_log if pd.Timestamp(s["ts"]).date() == d]
    rej = [r for c in engine.cores for r in c.rejections if pd.Timestamp(r["ts"]).date() == d]
    acct = engine.account()
    L = [f"# Paper trading daily report - {d}\n"]
    if md.is_synthetic:
        L.append("> Replay on SYNTHETIC data - engine rehearsal only.\n")
    L.append("## Market\n")
    if len(bars):
        o, h, l, c = bars.open.iloc[0], bars.high.max(), bars.low.min(), bars.close.iloc[-1]
        L.append(f"- NIFTY O/H/L/C: {o:,.1f} / {h:,.1f} / {l:,.1f} / {c:,.1f}  (day {100 * (c / o - 1):+.2f}%, "
                 f"range {100 * (h - l) / o:.2f}%)")
        big = bars.close.pct_change().abs().idxmax() if len(bars) > 1 else None
        if big is not None and pd.notna(big):
            L.append(f"- Largest bar move: {100 * bars.close.pct_change().iloc[big]:+.2f}% at {bars.ts.iloc[big]}")
    if ctx:
        L.append(f"- Regime (ex-ante): trend **{ctx.trend}**, volatility **{ctx.vol}** ({ctx.vol_dynamics}), "
                 f"India VIX {ctx.vix_open:.2f}, gap {100 * ctx.gap_pct:+.2f}%, tags {list(ctx.tags)}")
    L.append("\n## Signals\n")
    L.append(f"- Generated: {len(sigs)}; rejected: {len(rej)}")
    for r in rej:
        L.append(f"  - {r['ts']} {r.get('direction')} [{r['stage']}] {r['reasons']}")
    L.append("\n## Trades\n")
    L.append(f"- Entries today: {len(entered)}; exits today: {len(today)}; open positions: "
             f"{sum(len(c.positions) for c in engine.cores)}")
    for _, t in today.iterrows():
        L.append(f"  - {t['structure']} x{t['lots']}  {t['entry_ts']} -> {t['exit_ts']} ({t['exit_reason']}): "
                 f"gross {t['gross_pnl']:,.0f}, fees {t['fees']:,.0f}, slippage {t['slippage_rupees']:,.0f}, "
                 f"net **{t['net_pnl']:,.0f}** ({t['r_multiple']:+.2f}R)")
    for c in engine.cores:
        for p in c.positions:
            L.append(f"  - OPEN {p.proposal.built.structure.describe()} x{p.lots} since {p.entry_ts}, "
                     f"max risk {p.risk_rupees:,.0f}")
    L.append("\n## Performance\n")
    if len(today):
        L.append(f"- Gross P&L {today.gross_pnl.sum():,.0f} | fees {today.fees.sum():,.0f} | slippage "
                 f"{today.slippage_rupees.sum():,.0f} | **net {today.net_pnl.sum():,.0f}**")
    else:
        L.append("- No closed trades today.")
    L.append(f"- Account equity {acct['equity']:,.0f} (realized {acct['realized_pnl']:,.0f}, unrealized "
             f"{acct['unrealized_pnl']:,.0f}); open risk {acct['open_risk']:,.0f}; halted: {acct['halted']}")
    L.append("\n## Strategy behaviour (expected vs observed)\n")
    if len(trades):
        m = trade_metrics(trades)
        L.append(f"- Cumulative paper: {m['trades']} trades, win rate {m['win_rate']:.1%}, E[R] "
                 f"{m.get('expectancy_r', float('nan')):+.3f}, PF {m['profit_factor']:.2f}. "
                 "Compare with the backtest distribution in the dashboard 'Backtest vs Paper' tab; single days are noise.")
    else:
        L.append("- No paper trades yet.")
    L.append("\n## Anomalies\n")
    L.extend([f"- {a}" for a in engine.anomalies] or ["- None detected."])
    exit_issues = [r for c in engine.cores for r in c.rejections if r.get("stage") == "exit"
                   and pd.Timestamp(r["ts"]).date() == d]
    for r in exit_issues:
        L.append(f"- Exit problem: {r['reasons']} at {r['ts']}")
    L.append("\n## Conclusion\n")
    L.append("- No strategy changes are made from a single day's results. Any change requires a new registered "
             "experiment and must pass the promotion gate again.")
    engine.report_dir.mkdir(parents=True, exist_ok=True)
    path = engine.report_dir / f"{d}.md"
    path.write_text("\n".join(L) + "\n")
    return path
