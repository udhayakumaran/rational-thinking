"""Market-data value types shared by backtest, paper trading and data layers."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from .instruments import OptionContract

TICK = 0.05


@dataclass(frozen=True)
class Quote:
    contract: OptionContract
    ts: datetime
    bid: float = math.nan
    ask: float = math.nan
    ltp: float = math.nan
    volume: float = math.nan
    oi: float = math.nan
    iv: float = math.nan
    # True when bid/ask were NOT observed but estimated (EOD / OHLC-only data)
    spread_estimated: bool = False

    @property
    def has_two_sided(self) -> bool:
        return (math.isfinite(self.bid) and math.isfinite(self.ask)
                and self.bid > 0 and self.ask >= self.bid)

    @property
    def mid(self) -> float:
        if self.has_two_sided:
            return 0.5 * (self.bid + self.ask)
        return self.ltp

    @property
    def spread(self) -> float:
        return self.ask - self.bid if self.has_two_sided else math.nan

    @property
    def rel_spread(self) -> float:
        m = self.mid
        return self.spread / m if self.has_two_sided and m > 0 else math.nan


@dataclass(frozen=True)
class UnderlyingState:
    ts: datetime
    spot: float
    futures: float = math.nan
    vix: float = math.nan
