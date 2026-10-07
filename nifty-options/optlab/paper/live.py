"""Live MARKET-DATA plumbing for paper trading.

DESIGN RULE: this module (and the whole project) contains no code capable of
placing, modifying or cancelling orders. ``MarketDataSource`` exposes read
methods only. A vendor adapter must implement exactly these methods using the
vendor's market-data endpoints; it must not import or wrap any order API.
tests/test_no_live_trading.py scans the codebase for order-routing calls.

``LiveMarketData`` implements the common ``MarketData`` interface from an
in-memory store that the polling loop fills every bar, so strategies, risk and
execution simulation run unchanged.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from datetime import date, datetime

import pandas as pd

from ..core.calendar import TradingCalendar, lot_size_on
from ..core.instruments import OptionContract, Right
from ..core.market import Quote
from ..data.interfaces import BAR_COLUMNS, CHAIN_COLUMNS, MarketData


class MarketDataSource(ABC):
    """Read-only vendor interface. Implement per vendor once credentials exist."""

    @abstractmethod
    def index_bars(self, d: date, bar_minutes: int) -> pd.DataFrame: ...

    @abstractmethod
    def futures_bars(self, d: date, bar_minutes: int) -> pd.DataFrame: ...

    @abstractmethod
    def vix_value(self) -> float: ...

    @abstractmethod
    def option_chain(self, expiry: date) -> pd.DataFrame:
        """Current chain snapshot with CHAIN_COLUMNS (bid/ask required for realistic fills)."""

    @abstractmethod
    def expiries(self) -> list[tuple[date, int]]:
        """(expiry, lot_size) from the instrument master."""


class LiveMarketData(MarketData):
    is_synthetic = False

    def __init__(self, history: MarketData | None = None, bar_minutes: int = 5, underlying: str = "NIFTY"):
        self.history = history            # prior days (for regime context / SMAs)
        self.bar_minutes = bar_minutes
        self.underlying = underlying
        self.data_version = f"LIVE-{datetime.now():%Y%m%d}"
        self.calendar = TradingCalendar()
        self._bars: dict[date, pd.DataFrame] = {}
        self._vix: dict[date, dict] = {}
        self._chains: dict[tuple[datetime, date], pd.DataFrame] = {}
        self._exp: list[tuple[date, int]] = []

    # --- ingestion (called by the polling loop) -------------------------------
    def ingest(self, ts: datetime, bars_today: pd.DataFrame, vix: float, chains: dict[date, pd.DataFrame],
               expiries: list[tuple[date, int]]) -> None:
        self._bars[ts.date()] = bars_today[BAR_COLUMNS].copy()
        self._vix.setdefault(ts.date(), {})[ts] = vix
        for e, ch in chains.items():
            self._chains[(ts, e)] = ch[CHAIN_COLUMNS].copy()
        self._exp = sorted(expiries)

    # --- MarketData API --------------------------------------------------------
    def trading_days(self) -> list[date]:
        past = self.history.trading_days() if self.history else []
        return sorted(set(past) | set(self._bars))

    def underlying_bars(self, d: date) -> pd.DataFrame:
        if d in self._bars:
            return self._bars[d]
        return self.history.underlying_bars(d) if self.history else pd.DataFrame(columns=BAR_COLUMNS)

    def vix(self, d: date) -> pd.Series:
        if d in self._vix:
            return pd.Series(self._vix[d])
        return self.history.vix(d) if self.history else pd.Series(dtype=float)

    def expiries(self, d: date) -> list[date]:
        return [e for e, _ in self._exp if e >= d]

    def lot_size(self, d: date) -> int:
        nxt = [l for e, l in self._exp if e >= d]
        return nxt[0] if nxt else lot_size_on(d)

    def chain(self, ts: datetime, expiry: date) -> pd.DataFrame:
        return self._chains.get((ts, expiry), pd.DataFrame(columns=CHAIN_COLUMNS))

    def quote(self, ts: datetime, contract: OptionContract) -> Quote | None:
        ch = self._chains.get((ts, contract.expiry))
        if ch is None:
            return None
        r = ch[(ch.strike == contract.strike) & (ch.right == contract.right.value)]
        if r.empty:
            return None
        r = r.iloc[0]
        f = lambda x: float(x) if pd.notna(x) else math.nan
        return Quote(contract, ts, f(r.bid), f(r.ask), f(r.ltp), f(r.volume), f(r.oi), f(r.iv))
