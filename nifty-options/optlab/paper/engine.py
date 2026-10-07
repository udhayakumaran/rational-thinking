"""Paper-trading engine. PAPER ONLY - there is no order-routing code anywhere
in this project (tests/test_no_live_trading.py enforces it).

The engine drives the SAME ``TradingCore`` as the backtester, in portfolio
mode with the Rs 1L RiskManager shared across all promoted strategies, and
persists every signal, rejection, simulated order, fill, position, trade and
equity snapshot.

Data comes from any ``MarketData`` implementation: ``ReplayFeed`` replays
stored/synthetic history bar by bar (for rehearsal and engine tests);
``optlab.paper.live.LiveMarketData`` is filled from a market-data-only source.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session, sessionmaker

from ..backtest.engine import CoreConfig, TradingCore
from ..backtest.metrics import trade_metrics
from ..config import ROOT
from ..data.interfaces import MarketData
from ..db.models import (AccountEquity, DailyMetric, PaperFill, PaperOrder, PaperPosition, PaperTrade,
                         RejectedSignalRow, SignalRow)
from ..execution.costs import CostModel, Side
from ..execution.fills import FillModel
from ..research.experiments import jsonable
from ..risk.manager import RiskLimits, RiskManager
from ..strategies.base import Strategy, StrategyConfig
from ..strategies.indicators import vwap as vwap_fn
from ..strategies.regime import build_day_contexts


@dataclass
class PaperState:
    persisted_trades: dict = field(default_factory=dict)   # strategy label -> count persisted
    persisted_rej: dict = field(default_factory=dict)
    persisted_sig: dict = field(default_factory=dict)
    open_ids: set = field(default_factory=set)


class PaperEngine:
    def __init__(self, md: MarketData, configs: list[StrategyConfig], sessions: sessionmaker[Session],
                 costs: CostModel | None = None, fill_model: FillModel | None = None,
                 limits: RiskLimits | None = None, fill_delay_bars: int = 1, report_dir: Path | None = None):
        self.md = md
        self.sessions = sessions
        self.costs = costs or CostModel()
        self.fm = fill_model or FillModel()
        self.risk = RiskManager(limits or RiskLimits())
        self.cores = [TradingCore(Strategy(c, md), md, self.fm, self.costs, self.risk,
                                  CoreConfig(mode="portfolio", fill_delay_bars=fill_delay_bars), run_tag=f"paper{i}")
                      for i, c in enumerate(configs)]
        self.state = PaperState()
        self.report_dir = report_dir or (ROOT / "reports" / "paper")
        self._contexts = None
        self._day: date | None = None
        self._day_start_trades = 0
        self.anomalies: list[str] = []

    # ------------------------------------------------------------------ run
    def contexts(self):
        if self._contexts is None:
            self._contexts = build_day_contexts(self.md)
        return self._contexts

    def on_bar(self, ts: datetime) -> None:
        """Process one bar-end snapshot. Call in timestamp order."""
        d = ts.date()
        if self._day != d:
            if self._day is not None:
                self.end_of_day(self._day)
            self._start_day(d)
        bars = self.md.underlying_bars(d)
        bars = bars[bars["ts"] <= ts].reset_index(drop=True)
        if bars.empty or bars["ts"].iloc[-1] != ts:
            self.anomalies.append(f"{ts}: no underlying bar at snapshot time")
            return
        i = len(bars) - 1
        all_ts = self.md.underlying_bars(d)["ts"]
        is_last = ts == all_ts.iloc[-1]   # live: replace with session-close check
        ctx = self.contexts().get(d)
        spot = float(bars["close"].iloc[-1])
        vw = float(vwap_fn(bars).iloc[-1])
        for core in self.cores:
            sigs = [e for e in core.s.generate_signal(bars, ctx) if e.ts == ts]   # causal: bars <= ts only
            core.step(ts, i, spot, vw, sigs, ctx, is_last_bar=is_last)
        self._persist(ts)

    def _start_day(self, d: date) -> None:
        self._day = d
        self.risk.on_new_day(d)
        for core in self.cores:
            core.new_day(d)
        self._day_start_trades = sum(len(c.trades) for c in self.cores)
        self.anomalies = []

    def end_of_day(self, d: date) -> Path:
        for core in self.cores:
            core.end_of_day(d)
        self._persist(None)
        from .report import daily_report
        path = daily_report(self, d)
        return path

    def run_replay(self, start: date | None = None, end: date | None = None) -> None:
        for d in self.md.trading_days():
            if (start and d < start) or (end and d > end):
                continue
            for ts in self.md.underlying_bars(d)["ts"]:
                self.on_bar(ts)
        if self._day is not None:
            self.end_of_day(self._day)
            self._day = None

    # -------------------------------------------------------------- account
    def account(self) -> dict:
        unreal = sum(c.unrealized() for c in self.cores)
        realized = self.risk.equity - self.risk.limits.initial_capital
        return {"starting_capital": self.risk.limits.initial_capital, "equity": self.risk.equity + unreal,
                "realized_pnl": realized, "unrealized_pnl": unreal, "open_risk": self.risk.open_risk,
                "available_capital": self.risk.equity - self.risk.open_risk,
                "halted": self.risk.halted_reason, "daily_realized": self.risk.realized_today,
                "daily_loss_limit": -self.risk.limits.max_daily_loss_pct * self.risk.day_start_equity}

    # -------------------------------------------------------------- persist
    def _persist(self, ts: datetime | None) -> None:
        with self.sessions() as s:
            for core in self.cores:
                lbl = core.s.label
                n_sig = self.state.persisted_sig.get(lbl, 0)
                for sg in core.signals_log[n_sig:]:
                    s.add(SignalRow(ts=pd.Timestamp(sg["ts"]).to_pydatetime(), mode="paper", strategy=lbl,
                                    direction=sg["direction"], features=jsonable(sg["features"]), acted=False))
                self.state.persisted_sig[lbl] = len(core.signals_log)
                n_rej = self.state.persisted_rej.get(lbl, 0)
                for rj in core.rejections[n_rej:]:
                    s.add(RejectedSignalRow(ts=pd.Timestamp(rj["ts"]).to_pydatetime(), mode="paper", run_id=None,
                                            strategy=lbl, direction=str(rj.get("direction")), stage=rj["stage"],
                                            reasons=jsonable(rj["reasons"]), details=jsonable(rj.get("details", {}))))
                self.state.persisted_rej[lbl] = len(core.rejections)
                for pos in core.positions:
                    if pos.position_id not in self.state.open_ids:
                        self.state.open_ids.add(pos.position_id)
                        rec = dict(pos.entry_record)
                        rec["exit_conditions"] = core.s.cfg.exits.to_dict()
                        s.add(PaperPosition(position_id=pos.position_id, strategy=lbl, status="OPEN",
                                            opened_at=pos.entry_ts, record=jsonable(rec)))
                        self._orders(s, pos.position_id, pos.entry_ts, rec, "OPEN")
                n_tr = self.state.persisted_trades.get(lbl, 0)
                for tr in core.trades[n_tr:]:
                    pid = self._pid_for(core, tr)
                    s.add(PaperTrade(position_id=pid, strategy=lbl, entry_ts=tr["entry_ts"], exit_ts=tr["exit_ts"],
                                     net_pnl=float(tr["net_pnl"]), record=jsonable(tr)))
                    self._orders(s, pid, tr["exit_ts"], tr, "CLOSE")
                    pp = s.query(PaperPosition).filter_by(position_id=pid).one_or_none()
                    if pp is not None:
                        pp.status = "CLOSED"
                    self.state.open_ids.discard(pid)
                self.state.persisted_trades[lbl] = len(core.trades)
            # live marks for open positions
            for core in self.cores:
                for pos in core.positions:
                    pp = s.query(PaperPosition).filter_by(position_id=pos.position_id).one_or_none()
                    if pp is not None:
                        rec = dict(pp.record)
                        rec.update({"current_value": pos.last_value, "mark_ts": ts,
                                    "live_pnl": (pos.last_value - pos.entry_value_fill) * pos.proposal.lot_size * pos.lots
                                    if math.isfinite(pos.last_value) else None})
                        pp.record = jsonable(rec)
            if ts is not None:
                a = self.account()
                s.add(AccountEquity(ts=ts, mode="paper", equity=a["equity"], realized=a["realized_pnl"],
                                    unrealized=a["unrealized_pnl"], open_risk=a["open_risk"]))
            s.commit()

    @staticmethod
    def _pid_for(core: TradingCore, tr: dict) -> str:
        return tr.get("position_id") or f"{core.run_tag}-{tr['entry_ts']}"

    def _orders(self, s: Session, pid: str, ts, rec: dict, intent: str) -> None:
        ratios = rec["ratios"]
        lots, lot = rec["lots"], rec["lot_size"]
        pre = "entry" if intent == "OPEN" else "exit"
        prices, mids = rec[f"{pre}_prices"], rec[f"{pre}_mids"]
        bids, asks = rec.get(f"{pre}_bid") or [None] * len(ratios), rec.get(f"{pre}_ask") or [None] * len(ratios)
        ltps = rec.get("entry_ltp") if intent == "OPEN" else [None] * len(ratios)
        for j, r in enumerate(ratios):
            side = (Side.BUY if r > 0 else Side.SELL) if intent == "OPEN" else (Side.SELL if r > 0 else Side.BUY)
            units = abs(r) * lot * lots
            sym = f"{rec['expiry']}:{rec['strikes'][j]:g}{rec['rights'][j]}"
            o = PaperOrder(ts=pd.Timestamp(ts).to_pydatetime(), position_id=pid, symbol=sym, side=side.value,
                           units=units, intent=intent)
            s.add(o)
            s.flush()
            fees = self.costs.order_costs(side, prices[j], units, pd.Timestamp(ts).date()).total
            s.add(PaperFill(order_id=o.id, ts=pd.Timestamp(ts).to_pydatetime(), price=prices[j], mid=mids[j],
                            bid=_num(bids[j]), ask=_num(asks[j]), ltp=_num(ltps[j]) if ltps else None,
                            slippage_points=abs(prices[j] - mids[j]), fees=fees,
                            spread_estimated=bool(rec.get("spread_estimated", False))))

    def trades_df(self) -> pd.DataFrame:
        rows = [t for c in self.cores for t in c.trades]
        return pd.DataFrame(rows)


def _num(x):
    try:
        f = float(x)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None
