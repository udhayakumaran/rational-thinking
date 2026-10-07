"""Database-backed MarketData for REAL historical data, plus the writer used by loaders.

Data is keyed by ``data_version`` (content hash of the imported files), so an
experiment can always be re-run against exactly the data it used.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from functools import lru_cache

import pandas as pd
from sqlalchemy import text

from ..core.calendar import TradingCalendar, lot_size_on
from ..core.instruments import OptionContract, Right
from ..core.market import Quote
from ..db.session import make_engine
from .interfaces import BAR_COLUMNS, CHAIN_COLUMNS, MarketData


class StoredMarketData(MarketData):
    is_synthetic = False

    def __init__(self, url: str, data_version: str, underlying: str = "NIFTY", bar_minutes: int = 5,
                 spread_estimated: bool = False):
        self.engine = make_engine(url)
        self.data_version = data_version
        self.underlying = underlying
        self.bar_minutes = bar_minutes
        self.spread_estimated = spread_estimated
        with self.engine.connect() as c:
            days = c.execute(text(
                "SELECT DISTINCT date(ts) FROM underlying_candles WHERE data_version=:v AND kind='INDEX' "
                "AND underlying=:u ORDER BY 1"), {"v": data_version, "u": underlying}).fetchall()
            self._days = [date.fromisoformat(str(d[0])) for d in days]
            ex = pd.read_sql(text("SELECT expiry, lot_size, is_monthly FROM expiries WHERE data_version=:v "
                                  "AND underlying=:u ORDER BY expiry"), c, params={"v": data_version, "u": underlying})
        self._expiries = [pd.Timestamp(e).date() for e in ex.expiry]
        self._lot = {pd.Timestamp(e).date(): int(l) for e, l in zip(ex.expiry, ex.lot_size)}
        self.calendar = TradingCalendar(holidays=self._infer_holidays())

    def _infer_holidays(self) -> set[date]:
        if not self._days:
            return set()
        have = set(self._days)
        d, out = self._days[0], set()
        while d <= self._days[-1]:
            if d.weekday() < 5 and d not in have:
                out.add(d)
            d += timedelta(days=1)
        return out

    def trading_days(self) -> list[date]:
        return list(self._days)

    @lru_cache(maxsize=64)
    def _candles(self, d: date, kind: str) -> pd.DataFrame:
        q = text("SELECT ts, open, high, low, close, volume FROM underlying_candles WHERE data_version=:v AND "
                 "underlying=:u AND kind=:k AND interval_min=:m AND date(ts)=:d ORDER BY ts")
        with self.engine.connect() as c:
            df = pd.read_sql(q, c, params={"v": self.data_version, "u": self.underlying, "k": kind,
                                           "m": self.bar_minutes, "d": d.isoformat()})
        df["ts"] = pd.to_datetime(df["ts"]).dt.to_pydatetime() if len(df) else df["ts"]
        return df

    def underlying_bars(self, d: date) -> pd.DataFrame:
        idx = self._candles(d, "INDEX")
        fut = self._candles(d, "FUT")
        if len(idx) and len(fut):   # VWAP needs futures volume
            idx = idx.drop(columns="volume").merge(fut[["ts", "volume"]], on="ts", how="left")
        return idx[BAR_COLUMNS] if len(idx) else pd.DataFrame(columns=BAR_COLUMNS)

    def vix(self, d: date) -> pd.Series:
        v = self._candles(d, "VIX")
        return pd.Series(v["close"].to_numpy(), index=v["ts"]) if len(v) else pd.Series(dtype=float)

    def expiries(self, d: date) -> list[date]:
        return [e for e in self._expiries if e >= d][:8]

    def lot_size(self, d: date, expiry: date | None = None) -> int:
        if expiry is not None and expiry in self._lot:
            return self._lot[expiry]
        nxt = [e for e in self._expiries if e >= d]
        return self._lot.get(nxt[0]) if nxt else lot_size_on(d)

    @lru_cache(maxsize=8)
    def _day_quotes(self, d: date) -> dict:
        q = text("SELECT ts, expiry, strike, right, bid, ask, ltp, volume, oi, iv FROM option_quotes "
                 "WHERE data_version=:v AND underlying=:u AND date(ts)=:d")
        with self.engine.connect() as c:
            df = pd.read_sql(q, c, params={"v": self.data_version, "u": self.underlying, "d": d.isoformat()})
        if df.empty:
            return {}
        df["ts"] = pd.to_datetime(df["ts"])
        df["expiry"] = pd.to_datetime(df["expiry"]).dt.date
        out: dict = {}
        for (ts, ex), g in df.groupby(["ts", "expiry"]):
            out[(ts.to_pydatetime(), ex)] = g.drop(columns=["ts"]).reset_index(drop=True)
        return out

    def chain(self, ts: datetime, expiry: date) -> pd.DataFrame:
        g = self._day_quotes(ts.date()).get((ts, expiry))
        return g[CHAIN_COLUMNS] if g is not None else pd.DataFrame(columns=CHAIN_COLUMNS)

    def quote(self, ts: datetime, contract: OptionContract) -> Quote | None:
        g = self._day_quotes(ts.date()).get((ts, contract.expiry))
        if g is None:
            return None
        row = g[(g.strike == contract.strike) & (g.right == contract.right.value)]
        if row.empty:
            return None
        r = row.iloc[0]
        f = lambda x: float(x) if x is not None and pd.notna(x) else math.nan
        return Quote(contract, ts, bid=f(r.bid), ask=f(r.ask), ltp=f(r.ltp), volume=f(r.volume), oi=f(r.oi),
                     iv=f(r.iv), spread_estimated=self.spread_estimated or not (pd.notna(r.bid) and pd.notna(r.ask)))


def write_normalized(url: str, data_version: str, underlying: str, candles: dict[str, pd.DataFrame],
                     options: pd.DataFrame, expiries: pd.DataFrame, interval_min: int) -> dict:
    """Bulk-insert normalised frames. ``candles`` maps kind (INDEX/FUT/VIX) -> BAR_COLUMNS frame;
    ``options`` has ts, expiry, strike, right, open, high, low, bid, ask, ltp, volume, oi, iv;
    ``expiries`` has expiry, is_monthly, lot_size."""
    eng = make_engine(url)
    n = {}
    with eng.begin() as c:
        for kind, df in candles.items():
            if df is None or df.empty:
                continue
            d = df[BAR_COLUMNS].copy()
            d["underlying"], d["kind"], d["interval_min"], d["data_version"] = underlying, kind, interval_min, data_version
            d.to_sql("underlying_candles", c, if_exists="append", index=False)
            n[kind] = len(d)
        o = options.copy()
        o["underlying"], o["data_version"] = underlying, data_version
        for col in ("open", "high", "low", "bid", "ask", "ltp", "volume", "oi", "iv"):
            if col not in o:
                o[col] = None
        o[["ts", "underlying", "expiry", "strike", "right", "open", "high", "low", "bid", "ask", "ltp", "volume", "oi",
           "iv", "data_version"]].to_sql("option_quotes", c, if_exists="append", index=False, chunksize=50_000)
        n["options"] = len(o)
        e = expiries.copy()
        e["underlying"], e["data_version"] = underlying, data_version
        e[["underlying", "expiry", "is_monthly", "lot_size", "data_version"]].to_sql("expiries", c, if_exists="append",
                                                                                    index=False)
        n["expiries"] = len(e)
    return n
