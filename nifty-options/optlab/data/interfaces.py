"""The single read-only market-data interface used by research AND paper trading.

Everything downstream (signals, structure builders, backtester, paper engine)
talks only to ``MarketData``. Swapping a synthetic source for a real vendor
source therefore changes no strategy code.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime

import pandas as pd

from ..core.instruments import OptionContract
from ..core.market import Quote

BAR_COLUMNS = ["ts", "open", "high", "low", "close", "volume"]
CHAIN_COLUMNS = ["expiry", "strike", "right", "bid", "ask", "ltp", "volume", "oi", "iv"]


class MarketData(ABC):
    underlying: str = "NIFTY"
    #: identifies the exact dataset; stored with every experiment
    data_version: str = "unknown"
    #: synthetic results must never be compared with real-data results
    is_synthetic: bool = False
    bar_minutes: int = 5

    @abstractmethod
    def trading_days(self) -> list[date]: ...

    @abstractmethod
    def underlying_bars(self, d: date) -> pd.DataFrame:
        """Intraday bars for the index (``BAR_COLUMNS``; ts = bar END time).

        ``volume`` should be NIFTY-futures volume when available (needed for a
        true VWAP); NaN otherwise, in which case VWAP degrades to TWAP.
        """

    @abstractmethod
    def vix(self, d: date) -> pd.Series:
        """India VIX by bar end time for day ``d`` (may be empty)."""

    @abstractmethod
    def expiries(self, d: date) -> list[date]:
        """Option expiries tradable on ``d`` (ascending)."""

    @abstractmethod
    def chain(self, ts: datetime, expiry: date) -> pd.DataFrame:
        """Option chain snapshot at ``ts`` for ``expiry`` (``CHAIN_COLUMNS``)."""

    @abstractmethod
    def quote(self, ts: datetime, contract: OptionContract) -> Quote | None: ...

    @abstractmethod
    def lot_size(self, d: date, expiry: date | None = None) -> int:
        """Lot size of the contract series expiring on ``expiry`` (nearest series if None)."""

    def daily_bars(self) -> pd.DataFrame:
        """Daily OHLC built from intraday bars (override for speed)."""
        rows = []
        for d in self.trading_days():
            b = self.underlying_bars(d)
            if len(b):
                rows.append({"date": d, "open": b.open.iloc[0], "high": b.high.max(),
                             "low": b.low.min(), "close": b.close.iloc[-1]})
        return pd.DataFrame(rows).set_index("date")
