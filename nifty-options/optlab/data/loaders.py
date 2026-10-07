"""Importers that normalise vendor files into the canonical schema.

Supported now:
  * Generic intraday CSVs (index / futures / VIX candles + option candles or
    quotes) with a configurable column map - fits most vendor exports
    (TrueData, GDFL, broker historical APIs dumped to CSV).
  * NSE F&O bhavcopy (EOD), legacy format and the UDiFF format (2024+).
    EOD data has NO bid/ask: spreads are estimated and every resulting trade is
    flagged ``spread_estimated``; good for daily-horizon research only.

``data_version`` = 'REAL-' + content hash of all input files, so identical
inputs always map to the same version and experiments are reproducible.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, time, timedelta
from pathlib import Path

import pandas as pd

from ..core.calendar import TradingCalendar

DEFAULT_COLMAP = {
    "ts": "timestamp", "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume",
    "expiry": "expiry", "strike": "strike", "right": "option_type", "bid": "bid", "ask": "ask", "ltp": "close",
    "oi": "oi", "iv": "iv",
}


def content_version(paths: list[str | Path], prefix: str = "REAL") -> str:
    h = hashlib.sha1()
    for p in sorted(map(str, paths)):
        h.update(Path(p).read_bytes())
    return f"{prefix}-{h.hexdigest()[:12]}"


def _to_bar_end(ts: pd.Series, bar_minutes: int, label: str) -> pd.Series:
    ts = pd.to_datetime(ts)
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return ts + pd.Timedelta(minutes=bar_minutes) if label == "start" else ts


def load_candles_csv(path, bar_minutes: int, label: str = "start", colmap: dict | None = None) -> pd.DataFrame:
    cm = {**DEFAULT_COLMAP, **(colmap or {})}
    df = pd.read_csv(path)
    out = pd.DataFrame({"ts": _to_bar_end(df[cm["ts"]], bar_minutes, label)})
    for c in ("open", "high", "low", "close"):
        out[c] = df[cm[c]].astype(float)
    out["volume"] = df[cm["volume"]].astype(float) if cm["volume"] in df else float("nan")
    return out.sort_values("ts").reset_index(drop=True)


def load_options_csv(path, bar_minutes: int, label: str = "start", colmap: dict | None = None) -> pd.DataFrame:
    cm = {**DEFAULT_COLMAP, **(colmap or {})}
    df = pd.read_csv(path)
    out = pd.DataFrame({"ts": _to_bar_end(df[cm["ts"]], bar_minutes, label),
                        "expiry": pd.to_datetime(df[cm["expiry"]]).dt.date,
                        "strike": df[cm["strike"]].astype(float),
                        "right": df[cm["right"]].astype(str).str.upper().replace({"CALL": "CE", "PUT": "PE", "C": "CE", "P": "PE"})})
    for c in ("open", "high", "low", "bid", "ask", "ltp", "volume", "oi", "iv"):
        src = cm.get(c)
        out[c] = df[src].astype(float) if src in df else float("nan")
    return out


def expiries_from_options(opt: pd.DataFrame, lot_size_fn, calendar: TradingCalendar | None = None) -> pd.DataFrame:
    cal = calendar or TradingCalendar()
    ex = sorted(pd.Series(opt["expiry"]).unique())
    # monthly = last listed expiry of each calendar month
    s = pd.Series(ex)
    last_in_month = set(s.groupby([s.map(lambda e: e.year), s.map(lambda e: e.month)]).max())
    return pd.DataFrame({"expiry": ex, "is_monthly": [e in last_in_month for e in ex],
                         "lot_size": [lot_size_fn(e) for e in ex]})


# ----------------------------------------------------------------------- NSE
def load_nse_bhavcopy(path, underlying: str = "NIFTY") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (options, expiries) from one NSE F&O bhavcopy CSV (legacy or UDiFF)."""
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    if "TckrSymb" in df.columns:  # UDiFF
        df = df[(df["TckrSymb"] == underlying) & (df["FinInstrmTp"].isin(["IDO"]))]
        trade_date = pd.to_datetime(df["TradDt"]).dt.date
        opt = pd.DataFrame({
            "ts": [datetime.combine(d, time(15, 30)) for d in trade_date],
            "expiry": pd.to_datetime(df["XpryDt"]).dt.date, "strike": df["StrkPric"].astype(float),
            "right": df["OptnTp"].str.upper(), "open": df["OpnPric"], "high": df["HghPric"], "low": df["LwPric"],
            "ltp": df["ClsPric"], "settle": df["SttlmPric"], "volume": df["TtlTradgVol"], "oi": df["OpnIntrst"],
            "bid": float("nan"), "ask": float("nan"), "iv": float("nan")})
        lots = pd.DataFrame({"expiry": opt["expiry"], "lot_size": df["NewBrdLotQty"].astype(int).to_numpy()})
    else:  # legacy fo<DDMONYYYY>bhav.csv
        df = df[(df["SYMBOL"].str.strip() == underlying) & (df["INSTRUMENT"].str.strip() == "OPTIDX")]
        trade_date = pd.to_datetime(df["TIMESTAMP"], format="%d-%b-%Y").dt.date
        opt = pd.DataFrame({
            "ts": [datetime.combine(d, time(15, 30)) for d in trade_date],
            "expiry": pd.to_datetime(df["EXPIRY_DT"], format="%d-%b-%Y").dt.date,
            "strike": df["STRIKE_PR"].astype(float), "right": df["OPTION_TYP"].str.strip().str.upper(),
            "open": df["OPEN"], "high": df["HIGH"], "low": df["LOW"], "ltp": df["CLOSE"], "settle": df["SETTLE_PR"],
            "volume": df["CONTRACTS"], "oi": df["OPEN_INT"], "bid": float("nan"), "ask": float("nan"),
            "iv": float("nan")})
        lots = None
    opt = opt[opt["right"].isin(["CE", "PE"])].reset_index(drop=True)
    return opt, lots
