"""Option-structure construction: turns a direction into concrete legs.

Separate from signal generation so the SAME signal can be expressed as a long
option, an ATM debit spread, an ITM->OTM spread, a wider spread, etc.
Strike offsets are in strike *steps* measured toward OTM for the trade's
direction (0 = ATM, +1 = one strike OTM, -1 = one strike ITM).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime

import numpy as np
import pandas as pd

from ..core import instruments as ins
from ..core.instruments import Direction, Right, Structure
from ..data.interfaces import MarketData

KINDS = ("long_option", "debit_spread", "long_straddle", "long_strangle", "butterfly", "iron_condor")


@dataclass(frozen=True)
class StructureSpec:
    kind: str = "debit_spread"
    long_offset_steps: int = 0
    width_points: float = 100.0         # spreads; wing width for butterflies/condors
    short_offset_steps: int = 2         # condor short strikes distance from ATM (steps)
    min_dte: int = 0                    # minimum trading days to expiry (0 allows expiry day)
    expiry_rank: int = 0                # 0 = nearest eligible expiry, 1 = next, ...
    strike_step: float = 50.0

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"unknown structure kind {self.kind}")

    def label(self) -> str:
        if self.kind == "long_option":
            return f"long_opt[off{self.long_offset_steps:+d}]"
        if self.kind == "debit_spread":
            return f"debit_spread[off{self.long_offset_steps:+d},w{self.width_points:g}]"
        return f"{self.kind}[w{self.width_points:g}]"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class BuiltStructure:
    structure: Structure
    expiry: date
    atm_strike: float
    dte: int
    reason: str = ""


class StructureBuilder:
    def __init__(self, spec: StructureSpec, md: MarketData, calendar=None):
        self.spec = spec
        self.md = md
        self.calendar = calendar or getattr(md, "calendar", None)

    def select_expiry(self, d: date) -> tuple[date, int] | None:
        eligible = []
        for e in self.md.expiries(d):
            dte = self.calendar.trading_days_to_expiry(d, e) if self.calendar else (e - d).days
            if dte >= self.spec.min_dte:
                eligible.append((e, dte))
        if len(eligible) <= self.spec.expiry_rank:
            return None
        return eligible[self.spec.expiry_rank]

    def build(self, ts: datetime, direction: Direction, spot: float) -> BuiltStructure | str:
        """Returns a BuiltStructure, or a rejection reason string."""
        sel = self.select_expiry(ts.date())
        if sel is None:
            return "no_eligible_expiry"
        expiry, dte = sel
        chain = self.md.chain(ts, expiry)
        if chain.empty:
            return "empty_chain"
        strikes = np.sort(chain["strike"].unique())
        atm = float(strikes[np.argmin(np.abs(strikes - spot))])
        sp = self.spec
        step = sp.strike_step
        u = self.md.underlying

        def need(*ks: float) -> str | None:
            missing = [k for k in ks if not np.any(np.isclose(strikes, k))]
            return f"strike_not_listed:{missing}" if missing else None

        if sp.kind in ("long_option", "debit_spread"):
            if direction is Direction.NEUTRAL:
                return "neutral_signal_for_directional_structure"
            bull = direction is Direction.BULLISH
            k_long = atm + (1 if bull else -1) * sp.long_offset_steps * step
            if sp.kind == "long_option":
                if (err := need(k_long)):
                    return err
                st = ins.long_call(u, expiry, k_long) if bull else ins.long_put(u, expiry, k_long)
            else:
                k_short = k_long + (sp.width_points if bull else -sp.width_points)
                if (err := need(k_long, k_short)):
                    return err
                st = ins.bull_call_spread(u, expiry, k_long, k_short) if bull else \
                    ins.bear_put_spread(u, expiry, k_long, k_short)
        elif sp.kind == "long_straddle":
            if (err := need(atm)):
                return err
            st = ins.long_straddle(u, expiry, atm)
        elif sp.kind == "long_strangle":
            kp, kc = atm - sp.width_points, atm + sp.width_points
            if (err := need(kp, kc)):
                return err
            st = ins.long_strangle(u, expiry, kp, kc)
        elif sp.kind == "butterfly":
            k1, k3 = atm - sp.width_points, atm + sp.width_points
            if (err := need(k1, atm, k3)):
                return err
            st = ins.call_butterfly(u, expiry, k1, atm, k3)
        elif sp.kind == "iron_condor":
            ps, cs = atm - sp.short_offset_steps * step, atm + sp.short_offset_steps * step
            pl, cl = ps - sp.width_points, cs + sp.width_points
            if (err := need(pl, ps, cs, cl)):
                return err
            st = ins.iron_condor(u, expiry, pl, ps, cs, cl)
        else:  # pragma: no cover
            return f"unsupported_kind:{sp.kind}"
        return BuiltStructure(st, expiry, atm, dte)
