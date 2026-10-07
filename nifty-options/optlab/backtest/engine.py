"""Bar-by-bar options backtester and the shared ``TradingCore``.

``TradingCore.step`` contains ALL trading logic (signal -> structure ->
liquidity -> risk -> simulated fill -> marking -> exits -> settlement). The
backtester feeds it historical snapshots; the paper engine feeds it live
snapshots. Identical code paths are what make backtest-vs-paper comparison
meaningful.

Timing convention (no look-ahead):
  * a bar's timestamp is its END; signals use bars <= t
  * decisions taken at snapshot t are filled at snapshot t + ``fill_delay_bars``
    using the quotes AT THAT LATER snapshot (default delay = 1 bar)
  * decisions on the last bar of the session fill on that bar
"""
from __future__ import annotations

import itertools
import math
from dataclasses import asdict, dataclass, field
from datetime import date, datetime

import numpy as np
import pandas as pd

from ..core.instruments import Right
from ..core.pricing import bs_greeks, implied_vol, year_fraction
from ..core.calendar import minutes_to_expiry
from ..data.interfaces import MarketData
from ..execution.costs import CostBreakdown, CostModel, Side
from ..execution.fills import FillModel
from ..risk.manager import RiskLimits, RiskManager
from ..strategies.base import Proposal, Strategy
from ..strategies.exits import ExitState
from ..strategies.indicators import vwap as vwap_fn
from ..strategies.regime import DayContext, build_day_contexts
from ..strategies.signals import SignalEvent

RATE_R, RATE_Q = 0.065, 0.012


@dataclass(eq=False)
class OpenPosition:
    position_id: str
    strategy: str
    proposal: Proposal
    lots: int
    entry_ts: datetime
    entry_prices: list[float]
    entry_mids: list[float]
    entry_costs: CostBreakdown
    entry_slippage_rupees: float
    risk_rupees: float
    exit_state: ExitState
    entry_record: dict
    last_value: float = math.nan
    mfe_points: float = 0.0
    mae_points: float = 0.0

    @property
    def units_per_leg(self) -> list[int]:
        return [abs(l.ratio) * self.proposal.lot_size * self.lots for l in self.proposal.built.structure.legs]

    @property
    def entry_value_fill(self) -> float:
        return sum(l.ratio * p for l, p in zip(self.proposal.built.structure.legs, self.entry_prices))


@dataclass
class CoreConfig:
    mode: str = "research"          # research: always 1 lot, limits off | portfolio: full RiskManager
    fill_delay_bars: int = 1
    max_positions_per_strategy: int = 1


class TradingCore:
    def __init__(self, strategy: Strategy, md: MarketData, fill_model: FillModel, costs: CostModel,
                 risk: RiskManager, cfg: CoreConfig = CoreConfig(), run_tag: str = "bt"):
        self.s, self.md, self.fm, self.costs, self.risk, self.cfg = strategy, md, fill_model, costs, risk, cfg
        self.positions: list[OpenPosition] = []
        self.pending_entries: list[tuple[int, SignalEvent]] = []   # (due_bar_index, signal)
        self.pending_exits: list[tuple[int, OpenPosition, str]] = []
        self.trades: list[dict] = []
        self.rejections: list[dict] = []
        self.signals_log: list[dict] = []
        self._ids = itertools.count(1)
        self.run_tag = run_tag

    # ------------------------------------------------------------------ step
    def step(self, ts: datetime, i: int, spot: float, vw: float, new_signals: list[SignalEvent],
             ctx: DayContext | None, is_last_bar: bool) -> None:
        """Process one snapshot. ``i`` = bar index within the session, ``vw`` = session VWAP so far."""
        is_exp_day = bool(ctx and ctx.is_expiry_day)

        # 1) pending exits due now
        due = [x for x in self.pending_exits if x[0] <= i or is_last_bar]
        self.pending_exits = [x for x in self.pending_exits if not (x[0] <= i or is_last_bar)]
        for _, pos, reason in due:
            self._close(pos, ts, reason, spot)
        # 2) pending entries due now
        due_e = [x for x in self.pending_entries if x[0] <= i]
        self.pending_entries = [x for x in self.pending_entries if x[0] > i]
        for _, ev in due_e:
            self._try_open(ev, ts, spot, ctx)
        # 3) mark & evaluate exits
        exiting = {id(p) for _, p, _ in self.pending_exits}
        for pos in list(self.positions):
            if id(pos) in exiting:
                continue
            value = self._mark(pos, ts)
            if value is None:
                continue
            st = pos.exit_state
            if pos.entry_ts != ts:
                st.bars_held += 1
            reason = self.s.update(st, ts, value, spot, vw, is_exp_day and pos.proposal.built.expiry == ts.date(),
                                   is_last_bar)
            if reason:
                if self.cfg.fill_delay_bars == 0 or is_last_bar:
                    self._close(pos, ts, reason, spot)
                else:
                    self.pending_exits.append((i + self.cfg.fill_delay_bars, pos, reason))
        # 4) new signals
        for ev in new_signals:
            self.signals_log.append({"ts": ev.ts, "strategy": self.s.label, "direction": ev.direction.value,
                                     "reason": ev.reason, "features": ev.features})
            if is_last_bar:
                self._reject(ev, ts, "timing", ["signal_on_last_bar"])
            elif self.cfg.fill_delay_bars == 0:
                self._try_open(ev, ts, spot, ctx)
            else:
                self.pending_entries.append((i + self.cfg.fill_delay_bars, ev))

    def end_of_day(self, d: date) -> None:
        self.pending_entries.clear()

    # --------------------------------------------------------------- entries
    def _try_open(self, ev: SignalEvent, ts: datetime, spot: float, ctx: DayContext | None) -> None:
        if len(self.positions) >= self.cfg.max_positions_per_strategy:
            self._reject(ev, ts, "position", ["strategy_already_in_position"])
            return
        if self.cfg.mode == "portfolio":
            ok, why = self.risk.can_open()
            if not ok:
                self._reject(ev, ts, "risk", [why])
                return
        built = self.s.build_position(ev, ts, spot)
        if isinstance(built, str):
            self._reject(ev, ts, "structure", [built])
            return
        prop = self.s.price_position(ev, built, ts, self.fm, self.costs)
        if isinstance(prop, str):
            self._reject(ev, ts, "pricing", [prop], built=built)
            return
        liq = self.s.check_liquidity(prop)
        if liq:
            self._reject(ev, ts, "liquidity", liq, prop=prop)
            return
        risk_per_lot = self.s.calculate_max_risk(prop)
        # feasibility vs the INITIAL account (Rs 1L x risk %), independent of research P&L drift
        base_budget = self.risk.limits.initial_capital * self.risk.limits.risk_per_trade_pct
        budget_lots = int(base_budget // risk_per_lot) if risk_per_lot > 0 else 0
        if self.cfg.mode == "portfolio":
            dec = self.s.check_risk_limits(prop, self.risk)
            if not dec.approved:
                self._reject(ev, ts, "risk", list(dec.reasons), prop=prop)
                return
            lots = dec.lots
        else:
            lots = 1
        self._open(ev, prop, lots, ts, spot, ctx, budget_feasible=budget_lots >= 1)

    def _open(self, ev, prop: Proposal, lots: int, ts, spot, ctx, budget_feasible: bool) -> None:
        legs = prop.built.structure.legs
        lot = prop.lot_size
        costs = CostBreakdown()
        slip = 0.0
        for leg, px, mid in zip(legs, prop.fill_prices, prop.mids):
            units = abs(leg.ratio) * lot * lots
            side = Side.BUY if leg.ratio > 0 else Side.SELL
            costs = costs + self.costs.order_costs(side, px, units, ts.date())
            slip += abs(px - mid) * units
        risk_rupees = prop.max_risk_per_lot * lots
        pid = f"{self.run_tag}-{next(self._ids):06d}"
        rec = self._entry_record(ev, prop, lots, ts, spot, ctx, risk_rupees, budget_feasible)
        rec["position_id"] = pid
        pos = OpenPosition(pid, self.s.label, prop, lots, ts, list(prop.fill_prices), list(prop.mids), costs, slip,
                           risk_rupees, self.s.new_exit_state(prop, ts), rec)
        self.positions.append(pos)
        self.risk.on_open(risk_rupees)

    # ----------------------------------------------------------------- marks
    def _mark(self, pos: OpenPosition, ts: datetime) -> float | None:
        legs = pos.proposal.built.structure.legs
        v = 0.0
        for leg in legs:
            q = self.md.quote(ts, leg.contract)
            if q is None:
                return None
            v += leg.ratio * self.fm.mid(q)
        pos.last_value = v
        pnl_pts = v - pos.exit_state.entry_debit
        pos.mfe_points = max(pos.mfe_points, pnl_pts)
        pos.mae_points = min(pos.mae_points, pnl_pts)
        return v

    def unrealized(self, ts: datetime | None = None) -> float:
        tot = 0.0
        for p in self.positions:
            if math.isfinite(p.last_value):
                tot += (p.last_value - p.entry_value_fill) * p.proposal.lot_size * p.lots
        return tot

    # ----------------------------------------------------------------- exits
    def _close(self, pos: OpenPosition, ts: datetime, reason: str, spot: float, settle_spot: float | None = None):
        if pos not in self.positions:
            return
        legs = pos.proposal.built.structure.legs
        lot, lots = pos.proposal.lot_size, pos.lots
        exit_prices, exit_mids, costs, slip = [], [], CostBreakdown(), 0.0
        exit_quotes = []
        for leg, units in zip(legs, pos.units_per_leg):
            if settle_spot is not None:
                px = mid = leg.contract.intrinsic(settle_spot)
                if leg.ratio > 0:
                    costs = costs + self.costs.exercise_costs(px, units, leg.contract.expiry)
                exit_quotes.append(None)
            else:
                q = self.md.quote(ts, leg.contract)
                if q is None:
                    # cannot exit without a quote: keep position, retry next bar
                    self.rejections.append({"ts": ts, "stage": "exit", "strategy": pos.strategy,
                                            "reasons": [f"no_exit_quote:{leg.contract.symbol}"]})
                    return
                side = Side.SELL if leg.ratio > 0 else Side.BUY
                f = self.fm.fill(side, q)
                px, mid = f.price, f.mid
                costs = costs + self.costs.order_costs(side, px, units, ts.date())
                exit_quotes.append(q)
            exit_prices.append(px)
            exit_mids.append(mid)
            slip += abs(px - mid) * units
        self.positions.remove(pos)
        gross_pts = sum(l.ratio * (xp - ep) for l, xp, ep in zip(legs, exit_prices, pos.entry_prices))
        theo_pts = sum(l.ratio * (xm - em) for l, xm, em in zip(legs, exit_mids, pos.entry_mids))
        gross = gross_pts * lot * lots
        fees = pos.entry_costs.total + costs.total
        net = gross - fees
        self.risk.on_close(pos.risk_rupees, net)
        r = dict(pos.entry_record)
        exit_value = sum(l.ratio * p for l, p in zip(legs, exit_prices))
        r.update({
            "exit_ts": ts, "exit_reason": reason, "exit_spot": settle_spot if settle_spot is not None else spot,
            "exit_prices": exit_prices, "exit_mids": exit_mids,
            "exit_bid": [q.bid if q else None for q in exit_quotes],
            "exit_ask": [q.ask if q else None for q in exit_quotes],
            "exit_value": exit_value,
            "holding_minutes": (ts - pos.entry_ts).total_seconds() / 60.0,
            "bars_held": pos.exit_state.bars_held,
            "gross_pnl": gross, "fees": fees, "fees_entry": pos.entry_costs.total, "fees_exit": costs.total,
            "stt": pos.entry_costs.stt + costs.stt,
            "slippage_rupees": pos.entry_slippage_rupees + slip,
            "theoretical_pnl": theo_pts * lot * lots,
            "net_pnl": net,
            "return_on_risk": net / pos.risk_rupees if pos.risk_rupees > 0 else math.nan,
            "r_multiple": net / pos.risk_rupees if pos.risk_rupees > 0 else math.nan,
            "mfe_r": pos.mfe_points * lot * lots / pos.risk_rupees if pos.risk_rupees else math.nan,
            "mae_r": pos.mae_points * lot * lots / pos.risk_rupees if pos.risk_rupees else math.nan,
            "equity_after": self.risk.equity,
        })
        self.trades.append(r)

    def new_day(self, d: date) -> None:
        """Call at the start of each session, before any step()."""
        self.settle_expired(d)
        for pos in self.positions:
            pos.exit_state.days_held += 1

    def settle_expired(self, d: date) -> None:
        for pos in list(self.positions):
            e = pos.proposal.built.expiry
            if e < d:
                bars = self.md.underlying_bars(e)
                if not len(bars):
                    continue
                self._close(pos, bars["ts"].iloc[-1], "expiry_settlement", float(bars["close"].iloc[-1]),
                            settle_spot=float(bars["close"].iloc[-1]))

    # -------------------------------------------------------------- records
    def _reject(self, ev: SignalEvent, ts, stage: str, reasons: list[str], prop: Proposal | None = None, built=None):
        det = {"features": ev.features}
        b = prop.built if prop else built
        if b is not None:
            det["structure"] = b.structure.describe()
            det["expiry"] = str(b.expiry)
        if prop is not None:
            det.update({"max_risk_per_lot": prop.max_risk_per_lot, "max_reward_per_lot": prop.max_reward_per_lot,
                        "fill_prices": prop.fill_prices,
                        "bid": [q.bid for q in prop.quotes], "ask": [q.ask for q in prop.quotes]})
        self.rejections.append({"ts": ts, "signal_ts": ev.ts, "strategy": self.s.label,
                                "direction": ev.direction.value, "stage": stage, "reasons": reasons, "details": det})

    def _entry_record(self, ev, prop: Proposal, lots, ts, spot, ctx, risk_rupees, budget_feasible) -> dict:
        legs = prop.built.structure.legs
        greeks = []
        for leg, q in zip(legs, prop.quotes):
            t = year_fraction(minutes_to_expiry(ts, leg.contract.expiry))
            iv = q.iv if (q.iv == q.iv and q.iv > 0) else implied_vol(q.mid, spot, leg.contract.strike, t, RATE_R,
                                                                      RATE_Q, leg.contract.right is Right.CALL)
            if iv == iv and iv > 0:
                g = bs_greeks(spot, leg.contract.strike, t, RATE_R, RATE_Q, iv, leg.contract.right is Right.CALL)
                greeks.append({"iv": float(iv), **{k: float(v) for k, v in g.items()}})
            else:
                greeks.append({"iv": None, "delta": None, "gamma": None, "theta": None, "vega": None})
        net = {k: sum(l.ratio * (g[k] or 0.0) for l, g in zip(legs, greeks)) for k in ("delta", "gamma", "theta", "vega")}
        return {
            "strategy": self.s.label, "strategy_name": self.s.cfg.name, "config_hash": self.s.cfg.config_hash,
            "signal_ts": ev.ts, "entry_ts": ts, "entry_date": ts.date(), "direction": ev.direction.value,
            "entry_reason": ev.reason, "signal_features": ev.features,
            "spot": spot, "futures": None, "vix": ctx.vix_open if ctx else None,
            "regime": ctx.regime if ctx else None, "trend": ctx.trend if ctx else None,
            "vol_regime": ctx.vol if ctx else None, "day_tags": list(ctx.tags) if ctx else [],
            "structure": prop.built.structure.describe(), "structure_kind": prop.built.structure.name,
            "expiry": prop.built.expiry, "dte": prop.built.dte,
            "strikes": [l.contract.strike for l in legs], "rights": [l.contract.right.value for l in legs],
            "ratios": [l.ratio for l in legs],
            "entry_bid": [q.bid for q in prop.quotes], "entry_ask": [q.ask for q in prop.quotes],
            "entry_ltp": [q.ltp for q in prop.quotes], "entry_volume": [q.volume for q in prop.quotes],
            "entry_oi": [q.oi for q in prop.quotes], "spread_estimated": any(q.spread_estimated for q in prop.quotes),
            "entry_prices": prop.fill_prices, "entry_mids": prop.mids, "leg_greeks": greeks,
            "net_delta": net["delta"], "net_gamma": net["gamma"], "net_theta": net["theta"], "net_vega": net["vega"],
            "net_debit_points": prop.profile.net_premium,
            "max_loss_points": prop.profile.max_loss, "max_gain_points": prop.profile.max_gain,
            "breakevens": list(prop.profile.breakevens),
            "lot_size": prop.lot_size, "lots": lots, "quantity": lots * prop.lot_size,
            "risk_per_lot": prop.max_risk_per_lot, "max_reward_per_lot": prop.max_reward_per_lot,
            "account_risk": risk_rupees, "equity_before": self.risk.equity,
            "budget_feasible_at_1pct": budget_feasible,  # vs initial capital x risk_per_trade_pct
        }


# =============================================================================
@dataclass
class BacktestResult:
    trades: pd.DataFrame
    rejections: pd.DataFrame
    signals: pd.DataFrame
    daily: pd.DataFrame           # date, equity, realized, unrealized, open_risk
    meta: dict


class Backtester:
    def __init__(self, md: MarketData, fill_model: FillModel | None = None, costs: CostModel | None = None,
                 limits: RiskLimits | None = None, core_cfg: CoreConfig | None = None,
                 contexts: dict[date, DayContext] | None = None):
        self.md = md
        self.fm = fill_model or FillModel()
        self.costs = costs or CostModel()
        self.limits = limits or RiskLimits()
        self.core_cfg = core_cfg or CoreConfig()
        self.contexts = contexts if contexts is not None else build_day_contexts(md)

    def run(self, strategy: Strategy, start: date | None = None, end: date | None = None) -> BacktestResult:
        risk = RiskManager(self.limits)
        core = TradingCore(strategy, self.md, self.fm, self.costs, risk, self.core_cfg)
        daily = []
        days = [d for d in self.md.trading_days() if (start is None or d >= start) and (end is None or d <= end)]
        for d in days:
            risk.on_new_day(d)
            core.new_day(d)
            bars = self.md.underlying_bars(d).reset_index(drop=True)
            if bars.empty:
                continue
            ctx = self.contexts.get(d)
            sigs = strategy.generate_signal(bars, ctx)
            by_ts: dict = {}
            for ev in sigs:
                by_ts.setdefault(ev.ts, []).append(ev)
            n = len(bars)
            ts_list = bars["ts"].tolist()
            closes = bars["close"].to_numpy(dtype=float)
            vw = vwap_fn(bars).to_numpy(dtype=float)   # causal (cumulative)
            for i in range(n):
                ts = ts_list[i]
                new = by_ts.get(ts, [])
                if not new and not core.positions and not core.pending_entries and not core.pending_exits:
                    continue  # nothing to do on this bar: skip for speed
                core.step(ts, i, float(closes[i]), float(vw[i]), new, ctx, is_last_bar=(i == n - 1))
            core.end_of_day(d)
            daily.append({"date": d, "equity": risk.equity + core.unrealized(), "realized_equity": risk.equity,
                          "unrealized": core.unrealized(), "open_risk": risk.open_risk,
                          "halted": risk.halted_reason})
        # force-close anything still open at the end of the test window
        if core.positions and days:
            last = self.md.underlying_bars(days[-1])
            for pos in list(core.positions):
                core._close(pos, last["ts"].iloc[-1], "end_of_backtest", float(last["close"].iloc[-1]))
        meta = {"data_version": self.md.data_version, "is_synthetic": self.md.is_synthetic,
                "fill_model": self.fm.name.value, "mode": self.core_cfg.mode,
                "strategy": strategy.cfg.to_dict(), "label": strategy.label,
                "start": str(days[0]) if days else None, "end": str(days[-1]) if days else None,
                "n_days": len(days), "initial_capital": self.limits.initial_capital}
        return BacktestResult(pd.DataFrame(core.trades), pd.DataFrame(core.rejections),
                              pd.DataFrame(core.signals_log), pd.DataFrame(daily), meta)
