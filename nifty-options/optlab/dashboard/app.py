"""Paper-trading & research dashboard (read-only).

    streamlit run optlab/dashboard/app.py

There is intentionally no control in this UI that can place an order or
switch to live trading.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402
from sqlalchemy import select  # noqa: E402

from optlab.backtest.metrics import drawdown_stats, trade_metrics  # noqa: E402
from optlab.config import db_url, load_config  # noqa: E402
from optlab.db.models import (AccountEquity, BacktestRun, BacktestTradeRow, PaperPosition, PaperTrade,  # noqa: E402
                              RejectedSignalRow, SignalRow)
from optlab.db.session import session_factory  # noqa: E402
from optlab.paper.compare import compare  # noqa: E402
from optlab.research.experiments import Registry  # noqa: E402
from optlab.research.leaderboard import leaderboard  # noqa: E402

SERIES = ["#2a78d6", "#eb6834"]   # categorical slots 1-2 (validated reference palette)

st.set_page_config(page_title="NIFTY Options Lab (PAPER)", layout="wide")
st.title("NIFTY Options Lab - paper trading only")
st.caption("No live-trading capability exists in this system. All fills are simulated.")

cfg = load_config()
sessions = session_factory(db_url(cfg))
initial = float(cfg["capital"]["initial_capital"])


@st.cache_data(ttl=30)
def load():
    with sessions() as s:
        eq = pd.DataFrame([{"ts": r.ts, "equity": r.equity, "realized": r.realized, "unrealized": r.unrealized,
                            "open_risk": r.open_risk} for r in s.scalars(select(AccountEquity)
                                                                         .where(AccountEquity.mode == "paper"))])
        trades = pd.DataFrame([{**r.record, "strategy": r.strategy} for r in s.scalars(select(PaperTrade))])
        pos = pd.DataFrame([{**r.record, "status": r.status, "strategy": r.strategy}
                            for r in s.scalars(select(PaperPosition).where(PaperPosition.status == "OPEN"))])
        sig = pd.DataFrame([{"ts": r.ts, "strategy": r.strategy, "direction": r.direction}
                            for r in s.scalars(select(SignalRow).where(SignalRow.mode == "paper"))])
        rej = pd.DataFrame([{"ts": r.ts, "strategy": r.strategy, "stage": r.stage, "reasons": r.reasons}
                            for r in s.scalars(select(RejectedSignalRow).where(RejectedSignalRow.mode == "paper"))])
    return eq, trades, pos, sig, rej


def line(df, x, ys, title, names=None):
    fig = go.Figure()
    for i, y in enumerate(ys):
        fig.add_trace(go.Scatter(x=df[x], y=df[y], mode="lines", name=(names or ys)[i],
                                 line=dict(width=2, color=SERIES[i % 2])))
    fig.update_layout(title=title, height=320, margin=dict(l=10, r=10, t=40, b=10), hovermode="x unified",
                      showlegend=len(ys) > 1, xaxis=dict(showgrid=False), yaxis=dict(gridcolor="rgba(128,128,128,0.15)"))
    return fig


eq, trades, pos, sig, rej = load()
tab_acct, tab_pos, tab_strat, tab_cmp, tab_lb = st.tabs(
    ["Account & today", "Positions", "Strategies", "Backtest vs paper", "Research leaderboard"])

with tab_acct:
    last = eq.iloc[-1] if len(eq) else None
    c = st.columns(6)
    c[0].metric("Starting capital", f"Rs {initial:,.0f}")
    c[1].metric("Paper equity", f"Rs {last.equity:,.0f}" if last is not None else "-")
    c[2].metric("Available capital", f"Rs {last.equity - last.open_risk:,.0f}" if last is not None else "-")
    c[3].metric("Open risk", f"Rs {last.open_risk:,.0f}" if last is not None else "-")
    c[4].metric("Realized P&L", f"Rs {last.realized:,.0f}" if last is not None else "-")
    c[5].metric("Unrealized P&L", f"Rs {last.unrealized:,.0f}" if last is not None else "-")
    if len(eq):
        st.plotly_chart(line(eq, "ts", ["equity"], "Paper equity"), use_container_width=True)
    today = eq.ts.max().date() if len(eq) else date.today()
    st.subheader(f"Today ({today})")
    tt = trades[pd.to_datetime(trades.exit_ts).dt.date == today] if len(trades) else trades
    ts_sig = sig[pd.to_datetime(sig.ts).dt.date == today] if len(sig) else sig
    pnl_today = float(tt.net_pnl.sum()) if len(tt) else 0.0
    limit = -cfg["risk"]["max_daily_loss_pct"] * (last.equity if last is not None else initial)
    c = st.columns(6)
    c[0].metric("Signals", len(ts_sig))
    c[1].metric("Trades closed", len(tt))
    c[2].metric("Wins", int((tt.net_pnl > 0).sum()) if len(tt) else 0)
    c[3].metric("Losses", int((tt.net_pnl <= 0).sum()) if len(tt) else 0)
    c[4].metric("Net P&L", f"Rs {pnl_today:,.0f}")
    c[5].metric("Daily loss limit", "BREACHED" if pnl_today <= limit else "OK", f"limit Rs {limit:,.0f}",
                delta_color="off")
    if len(rej):
        st.markdown("**Rejected signals (latest 50)**")
        st.dataframe(rej.sort_values("ts", ascending=False).head(50), use_container_width=True)

with tab_pos:
    if len(pos):
        show = pos[["strategy", "structure", "expiry", "strikes", "entry_ts", "entry_prices", "current_value",
                    "account_risk", "max_reward_per_lot", "lots", "live_pnl", "exit_conditions"]].copy()
        st.dataframe(show, use_container_width=True)
    else:
        st.info("No open paper positions.")

with tab_strat:
    if len(trades):
        rows = []
        for s_name, g in trades.groupby("strategy"):
            m = trade_metrics(g)
            dd = drawdown_stats((initial + g.sort_values("exit_ts").net_pnl.cumsum()).reset_index(drop=True))
            rows.append({"strategy": s_name, "trades": m["trades"], "win_rate": m["win_rate"],
                         "expectancy_rs": m["expectancy"], "expectancy_r": m.get("expectancy_r"),
                         "profit_factor": m["profit_factor"], "avg_winner": m["avg_winner"],
                         "avg_loser": m["avg_loser"], "max_drawdown_pct": dd["max_drawdown_pct"]})
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
        st.dataframe(trades.sort_values("exit_ts", ascending=False)[
            ["strategy", "entry_ts", "exit_ts", "structure", "lots", "net_pnl", "r_multiple", "fees",
             "slippage_rupees", "exit_reason"]].head(100), use_container_width=True)
    else:
        st.info("No closed paper trades yet.")

with tab_cmp:
    reg = Registry(sessions)
    with sessions() as s:
        runs = pd.DataFrame([{"run_id": r.run_id, "experiment": r.experiment_id, "variant": r.variant,
                              "synthetic": r.is_synthetic, "label": r.params.get("name")}
                             for r in s.scalars(select(BacktestRun).where(BacktestRun.variant.like("%:realistic")))])
    if len(runs) and len(trades):
        choice = st.selectbox("Backtest run to compare against", runs.run_id)
        strat = st.selectbox("Paper strategy", sorted(trades.strategy.unique()))
        with sessions() as s:
            bt = pd.DataFrame([r.record for r in s.scalars(select(BacktestTradeRow).where(BacktestTradeRow.run_id == choice))])
        res = compare(bt, trades[trades.strategy == strat])
        st.table(pd.DataFrame({"backtest": res["backtest"], "paper": res["paper"]}))
        if res.get("warning"):
            st.warning(res["warning"])
        st.write({k: res.get(k) for k in ("paper_mean_r_percentile_in_backtest", "paper_consistency",
                                          "slippage_ratio_paper_vs_backtest")})
    else:
        st.info("Needs at least one completed backtest run and some paper trades.")

with tab_lb:
    lb = leaderboard(Registry(sessions))
    if len(lb):
        st.markdown("Ranked by robustness score (never by total return). **Synthetic rows validate the pipeline only.**")
        st.dataframe(lb, use_container_width=True)
    else:
        st.info("No completed experiments yet.")
