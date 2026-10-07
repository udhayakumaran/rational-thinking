"""Option contracts, legs, multi-leg structures and exact expiry risk profiles.

All per-structure quantities here are in index POINTS per one unit of the
structure (i.e. per 1 share of the lot multiplier). Multiply by
``lot_size * lots`` to obtain rupees.

The expiry payoff of any European option structure is piecewise linear in the
underlying price S, with kinks only at strikes. So the exact max loss, max
gain and breakevens follow from evaluating the payoff at S=0, at every strike,
and from the slope beyond the highest strike.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
import math
from typing import Mapping, Sequence


class Right(str, Enum):
    CALL = "CE"
    PUT = "PE"


class Direction(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


@dataclass(frozen=True, order=True)
class OptionContract:
    underlying: str
    expiry: date
    strike: float
    right: Right

    @property
    def symbol(self) -> str:
        return f"{self.underlying}{self.expiry:%y%m%d}{self.strike:g}{self.right.value}"

    def intrinsic(self, spot: float) -> float:
        if self.right is Right.CALL:
            return max(spot - self.strike, 0.0)
        return max(self.strike - spot, 0.0)


@dataclass(frozen=True)
class Leg:
    contract: OptionContract
    ratio: int  # signed units per one structure: +1 long, -1 short, +2 ...

    def __post_init__(self) -> None:
        if self.ratio == 0:
            raise ValueError("leg ratio must be non-zero")

    @property
    def is_long(self) -> bool:
        return self.ratio > 0


@dataclass(frozen=True)
class Structure:
    name: str
    legs: tuple[Leg, ...]

    def __post_init__(self) -> None:
        if not self.legs:
            raise ValueError("structure needs at least one leg")

    @property
    def expiries(self) -> set[date]:
        return {leg.contract.expiry for leg in self.legs}

    @property
    def strikes(self) -> list[float]:
        return sorted({leg.contract.strike for leg in self.legs})

    def describe(self) -> str:
        parts = []
        for leg in self.legs:
            side = "+" if leg.ratio > 0 else "-"
            n = abs(leg.ratio)
            parts.append(f"{side}{'' if n == 1 else n}{leg.contract.strike:g}{leg.contract.right.value}")
        return f"{self.name}[{' '.join(parts)} exp {next(iter(self.expiries))}]"


def net_premium(structure: Structure, prices: Sequence[float]) -> float:
    """Net premium per structure unit; positive = debit paid, negative = credit."""
    _check_prices(structure, prices)
    return sum(leg.ratio * p for leg, p in zip(structure.legs, prices))


def expiry_value(structure: Structure, spot: float) -> float:
    """Value of the structure at expiry (per unit, before premium)."""
    return sum(leg.ratio * leg.contract.intrinsic(spot) for leg in structure.legs)


def pnl_at_expiry(structure: Structure, prices: Sequence[float], spot: float) -> float:
    return expiry_value(structure, spot) - net_premium(structure, prices)


def mark_value(structure: Structure, prices: Sequence[float]) -> float:
    """Liquidation value of the structure given current per-leg prices."""
    return net_premium(structure, prices)


@dataclass(frozen=True)
class RiskProfile:
    net_premium: float           # + debit / - credit
    max_loss: float              # positive number of points; math.inf if unbounded
    max_gain: float              # math.inf if unbounded
    breakevens: tuple[float, ...]

    @property
    def defined_risk(self) -> bool:
        return math.isfinite(self.max_loss)

    @property
    def reward_to_risk(self) -> float:
        if not self.defined_risk or self.max_loss <= 0:
            return math.nan
        return self.max_gain / self.max_loss


def risk_profile(structure: Structure, prices: Sequence[float]) -> RiskProfile:
    """Exact expiry risk profile of a single-expiry structure."""
    if len(structure.expiries) != 1:
        raise ValueError("risk_profile only supports single-expiry structures")
    _check_prices(structure, prices)
    prem = net_premium(structure, prices)
    xs = [0.0] + structure.strikes
    ys = [expiry_value(structure, x) - prem for x in xs]
    # slope for S above the highest strike: every call contributes +ratio
    slope_right = sum(l.ratio for l in structure.legs if l.contract.right is Right.CALL)

    min_y, max_y = min(ys), max(ys)
    max_loss = math.inf if slope_right < 0 else max(0.0, -min_y)
    max_gain = math.inf if slope_right > 0 else max(0.0, max_y)

    bes: list[float] = []
    for (x0, y0), (x1, y1) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
        if y0 == 0.0 and x0 > 0:
            bes.append(x0)
        if (y0 < 0 < y1) or (y0 > 0 > y1):
            bes.append(x0 + (x1 - x0) * (-y0) / (y1 - y0))
    if ys[-1] == 0.0 and xs[-1] > 0:
        bes.append(xs[-1])
    if slope_right != 0 and ys[-1] != 0 and (ys[-1] > 0) != (slope_right > 0):
        bes.append(xs[-1] - ys[-1] / slope_right)
    bes_t = tuple(sorted({round(b, 10) for b in bes}))
    return RiskProfile(net_premium=prem, max_loss=max_loss, max_gain=max_gain, breakevens=bes_t)


def _check_prices(structure: Structure, prices: Sequence[float]) -> None:
    if len(prices) != len(structure.legs):
        raise ValueError(f"expected {len(structure.legs)} prices, got {len(prices)}")


# ---------------------------------------------------------------------------
# Convenience constructors for the structures under research
# ---------------------------------------------------------------------------

def _c(u: str, e: date, k: float, r: Right) -> OptionContract:
    return OptionContract(u, e, float(k), r)


def long_call(u: str, e: date, k: float) -> Structure:
    return Structure("long_call", (Leg(_c(u, e, k, Right.CALL), 1),))


def long_put(u: str, e: date, k: float) -> Structure:
    return Structure("long_put", (Leg(_c(u, e, k, Right.PUT), 1),))


def bull_call_spread(u: str, e: date, k_long: float, k_short: float) -> Structure:
    if not k_short > k_long:
        raise ValueError("bull call spread needs k_short > k_long")
    return Structure("bull_call_spread", (Leg(_c(u, e, k_long, Right.CALL), 1), Leg(_c(u, e, k_short, Right.CALL), -1)))


def bear_put_spread(u: str, e: date, k_long: float, k_short: float) -> Structure:
    if not k_short < k_long:
        raise ValueError("bear put spread needs k_short < k_long")
    return Structure("bear_put_spread", (Leg(_c(u, e, k_long, Right.PUT), 1), Leg(_c(u, e, k_short, Right.PUT), -1)))


def long_straddle(u: str, e: date, k: float) -> Structure:
    return Structure("long_straddle", (Leg(_c(u, e, k, Right.CALL), 1), Leg(_c(u, e, k, Right.PUT), 1)))


def long_strangle(u: str, e: date, k_put: float, k_call: float) -> Structure:
    if not k_call > k_put:
        raise ValueError("strangle needs k_call > k_put")
    return Structure("long_strangle", (Leg(_c(u, e, k_put, Right.PUT), 1), Leg(_c(u, e, k_call, Right.CALL), 1)))


def call_butterfly(u: str, e: date, k1: float, k2: float, k3: float) -> Structure:
    if not k1 < k2 < k3:
        raise ValueError("butterfly needs k1 < k2 < k3")
    return Structure("call_butterfly", (
        Leg(_c(u, e, k1, Right.CALL), 1), Leg(_c(u, e, k2, Right.CALL), -2), Leg(_c(u, e, k3, Right.CALL), 1)))


def iron_butterfly(u: str, e: date, k_put_wing: float, k_body: float, k_call_wing: float) -> Structure:
    if not k_put_wing < k_body < k_call_wing:
        raise ValueError("iron butterfly strikes out of order")
    return Structure("iron_butterfly", (
        Leg(_c(u, e, k_put_wing, Right.PUT), 1), Leg(_c(u, e, k_body, Right.PUT), -1),
        Leg(_c(u, e, k_body, Right.CALL), -1), Leg(_c(u, e, k_call_wing, Right.CALL), 1)))


def iron_condor(u: str, e: date, kp_long: float, kp_short: float, kc_short: float, kc_long: float) -> Structure:
    if not kp_long < kp_short < kc_short < kc_long:
        raise ValueError("iron condor strikes out of order")
    return Structure("iron_condor", (
        Leg(_c(u, e, kp_long, Right.PUT), 1), Leg(_c(u, e, kp_short, Right.PUT), -1),
        Leg(_c(u, e, kc_short, Right.CALL), -1), Leg(_c(u, e, kc_long, Right.CALL), 1)))


def structure_from_mapping(name: str, legs: Mapping[OptionContract, int]) -> Structure:
    return Structure(name, tuple(Leg(c, r) for c, r in legs.items()))
