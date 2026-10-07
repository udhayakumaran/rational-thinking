"""The common Strategy interface.

A Strategy = SignalGenerator + StructureBuilder + ExitConfig + LiquidityRules.
It never fills orders and never sizes positions by itself: execution lives in
``optlab.execution`` and sizing/limits in ``optlab.risk``. The same Strategy
object is driven by the backtester and by the paper-trading engine.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime

from ..core.instruments import Direction, RiskProfile, risk_profile
from ..core.market import Quote
from ..data.interfaces import MarketData
from ..execution.costs import CostModel, Side
from ..execution.fills import FillModel
from ..risk.manager import RiskManager, SizingDecision
from .exits import ExitConfig, ExitState, check_exit
from .regime import DayContext
from .signals import SignalEvent, make_signal
from .structures import BuiltStructure, StructureBuilder, StructureSpec


@dataclass(frozen=True)
class LiquidityRules:
    require_two_sided: bool = True
    max_rel_spread: float = 0.05     # (ask-bid)/mid per leg
    min_premium: float = 2.0         # per leg, points
    min_oi: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    version: str = "1"
    signal: str = "orb"
    signal_params: dict = field(default_factory=dict)
    structure: StructureSpec = field(default_factory=StructureSpec)
    exits: ExitConfig = field(default_factory=ExitConfig)
    liquidity: LiquidityRules = field(default_factory=LiquidityRules)

    def to_dict(self) -> dict:
        return {"name": self.name, "version": self.version, "signal": self.signal,
                "signal_params": dict(self.signal_params), "structure": self.structure.to_dict(),
                "exits": self.exits.to_dict(), "liquidity": self.liquidity.to_dict()}

    @property
    def config_hash(self) -> str:
        return hashlib.sha1(json.dumps(self.to_dict(), sort_keys=True, default=str).encode()).hexdigest()[:12]

    @classmethod
    def from_dict(cls, d: dict) -> "StrategyConfig":
        return cls(name=d["name"], version=str(d.get("version", "1")), signal=d.get("signal", "orb"),
                   signal_params=dict(d.get("signal_params", {})),
                   structure=StructureSpec(**d.get("structure", {})),
                   exits=ExitConfig(**d.get("exits", {})),
                   liquidity=LiquidityRules(**d.get("liquidity", {})))


@dataclass
class Proposal:
    """A fully priced candidate position, before sizing."""
    signal: SignalEvent
    built: BuiltStructure
    quotes: list[Quote]
    fill_prices: list[float]          # per-unit simulated entry prices, per leg
    mids: list[float]
    profile: RiskProfile              # computed on simulated fill prices
    est_costs_per_lot: float          # entry + exit (estimated) rupees per lot
    lot_size: int

    @property
    def max_risk_per_lot(self) -> float:
        return self.profile.max_loss * self.lot_size + self.est_costs_per_lot

    @property
    def max_reward_per_lot(self) -> float:
        return self.profile.max_gain * self.lot_size - self.est_costs_per_lot


class Strategy:
    def __init__(self, cfg: StrategyConfig, md: MarketData):
        self.cfg = cfg
        self.md = md
        self.signal_gen = make_signal(cfg.signal, cfg.signal_params, md.bar_minutes)
        self.builder = StructureBuilder(cfg.structure, md)

    @property
    def label(self) -> str:
        return f"{self.cfg.name}:{self.cfg.structure.label()}:{self.cfg.exits.label()}"

    # 1. signal ---------------------------------------------------------------
    def generate_signal(self, bars, ctx: DayContext | None) -> list[SignalEvent]:
        return self.signal_gen.compute_day(bars, ctx)

    # 2. structure ------------------------------------------------------------
    def build_position(self, ev: SignalEvent, ts: datetime, spot: float) -> BuiltStructure | str:
        return self.builder.build(ts, ev.direction, spot)

    def price_position(self, ev: SignalEvent, built: BuiltStructure, ts: datetime, fill_model: FillModel,
                       costs: CostModel) -> Proposal | str:
        quotes = []
        for leg in built.structure.legs:
            q = self.md.quote(ts, leg.contract)
            if q is None:
                return f"no_quote:{leg.contract.symbol}"
            quotes.append(q)
        lot = self.md.lot_size(ts.date())
        try:
            fills = [fill_model.fill(Side.BUY if leg.ratio > 0 else Side.SELL, q)
                     for leg, q in zip(built.structure.legs, quotes)]
        except ValueError as e:
            return f"unfillable:{e}"
        prices = [f.price for f in fills]
        prof = risk_profile(built.structure, prices)
        est = 0.0
        for leg, f in zip(built.structure.legs, fills):
            units = abs(leg.ratio) * lot
            side_in = Side.BUY if leg.ratio > 0 else Side.SELL
            side_out = Side.SELL if leg.ratio > 0 else Side.BUY
            est += costs.order_costs(side_in, f.price, units, ts.date()).total
            est += costs.order_costs(side_out, f.price, units, ts.date()).total
        return Proposal(ev, built, quotes, prices, [f.mid for f in fills], prof, est, lot)

    # 3. risk / reward --------------------------------------------------------
    @staticmethod
    def calculate_max_risk(p: Proposal) -> float:
        return p.max_risk_per_lot

    @staticmethod
    def calculate_expected_reward(p: Proposal) -> float:
        return p.max_reward_per_lot

    # 4. filters ----------------------------------------------------------------
    def check_liquidity(self, p: Proposal) -> list[str]:
        r = self.cfg.liquidity
        reasons = []
        for q in p.quotes:
            sym = q.contract.symbol
            if r.require_two_sided and not q.has_two_sided:
                reasons.append(f"not_two_sided:{sym}")
                continue
            if q.has_two_sided and q.rel_spread > r.max_rel_spread:
                reasons.append(f"wide_spread:{sym}:{q.rel_spread:.3f}")
            if q.mid < r.min_premium:
                reasons.append(f"premium_below_min:{sym}:{q.mid:.2f}")
            if r.min_oi is not None and math.isfinite(q.oi) and q.oi < r.min_oi:
                reasons.append(f"low_oi:{sym}")
        if not p.profile.defined_risk:
            reasons.append("undefined_risk_structure")
        if p.profile.max_loss <= 0:
            reasons.append("non_positive_max_loss(arbitrage_or_bad_quote)")
        return reasons

    @staticmethod
    def check_risk_limits(p: Proposal, risk: RiskManager) -> SizingDecision:
        return risk.check(p.max_risk_per_lot)

    # 5. lifecycle --------------------------------------------------------------
    def new_exit_state(self, p: Proposal, ts: datetime) -> ExitState:
        sign = {Direction.BULLISH: 1, Direction.BEARISH: -1}.get(p.signal.direction, 0)
        entry_mid_value = sum(l.ratio * m for l, m in zip(p.built.structure.legs, p.mids))
        max_profit = p.profile.max_gain + p.profile.net_premium - entry_mid_value \
            if math.isfinite(p.profile.max_gain) else math.inf
        return ExitState(entry_debit=entry_mid_value, max_profit=max_profit, direction_sign=sign,
                         entry_ts=ts, features=dict(p.signal.features))

    def update(self, st: ExitState, ts: datetime, value: float, spot: float, vwap: float | None,
               is_expiry_day: bool, is_last_bar: bool) -> str | None:
        return check_exit(self.cfg.exits, st, ts, value, spot, vwap, is_expiry_day, is_last_bar)
