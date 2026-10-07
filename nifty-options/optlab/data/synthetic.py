"""SYNTHETIC NIFTY + option-chain generator - for ENGINE VALIDATION ONLY.

Nothing produced from this module is evidence about the real market. Every
dataset carries ``is_synthetic = True`` and a ``data_version`` beginning with
``SYNTH-``; the experiment registry and leaderboard keep such results apart.

Two uses:
  * NEGATIVE CONTROL (``edge_strength = 0``): a driftless random walk with
    fairly priced options. Any strategy should show ~zero gross / negative net
    expectancy. A "profitable" strategy here means look-ahead or a P&L bug.
  * POSITIVE CONTROL (``edge_strength > 0``): plants intraday continuation
    after an opening-range breakout. The pipeline must be able to detect it.

Model: 5-minute log-returns with a Markov volatility regime (daily), U-shaped
intraday variance profile, overnight gaps and rare jumps. Options are priced
with Black-Scholes on a skewed smile around an implied vol of
``regime_vol * (1 + vrp)``; bid/ask spreads widen for cheap/far-OTM strikes.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

from ..core.calendar import TradingCalendar, iter_session_bars, lot_size_on, minutes_to_expiry
from ..core.instruments import OptionContract, Right
from ..core.market import TICK, Quote
from ..core.pricing import bs_greeks, bs_price, bs_price_scalar, year_fraction
from .interfaces import CHAIN_COLUMNS, MarketData


@dataclass(frozen=True)
class SyntheticConfig:
    start: date = date(2023, 1, 2)
    end: date = date(2025, 12, 31)
    seed: int = 7
    spot0: float = 18_000.0
    bar_minutes: int = 5
    annual_drift: float = 0.0
    regime_vols: tuple[float, ...] = (0.10, 0.14, 0.22)
    regime_stay_prob: float = 0.97
    overnight_var_frac: float = 0.20
    jump_prob_per_day: float = 0.01
    jump_size_sd: float = 0.02
    vrp: float = 0.10              # implied vol premium over regime vol
    skew: float = 0.8              # put-skew slope in log-moneyness
    smile: float = 2.0
    r: float = 0.065
    q: float = 0.012
    strike_step: float = 50.0
    strikes_each_side: int = 30
    edge_strength: float = 0.0     # planted ORB continuation, in per-bar sigmas
    orb_bars: int = 3
    lot_size: int | None = None    # None -> calendar schedule


class SyntheticMarketData(MarketData):
    is_synthetic = True

    def __init__(self, cfg: SyntheticConfig = SyntheticConfig()):
        self.cfg = cfg
        self.bar_minutes = cfg.bar_minutes
        self.calendar = TradingCalendar()
        h = hashlib.sha1(repr(sorted(asdict(cfg).items())).encode()).hexdigest()[:10]
        kind = "POSCTRL" if cfg.edge_strength > 0 else "NULL"
        self.data_version = f"SYNTH-{kind}-{h}"
        self._days = self.calendar.trading_days(cfg.start, cfg.end)
        # variance clock: options are priced on the same clock the simulator
        # uses to accrue variance (trading time), so the null control is fair.
        self._clock_days = self.calendar.trading_days(cfg.start, cfg.end + timedelta(days=120))
        self._day_idx = {d: i for i, d in enumerate(self._clock_days)}
        self._bars, self._vix = self._simulate()
        self._bar_idx = {t: i for t, i in zip(self._bars.ts, self._bars.groupby("date").cumcount())}
        self._by_day = {d: g.reset_index(drop=True) for d, g in self._bars.groupby("date")}
        self._spot_at = dict(zip(self._bars.ts, self._bars.close))
        self._iv_at = dict(zip(self._bars.ts, self._bars.atm_iv))
        self._open_spot = {d: g.open.iloc[0] for d, g in self._by_day.items()}
        all_exp = self.calendar.weekly_expiries(cfg.start, cfg.end + timedelta(days=100))
        months = {(e.year, e.month) for e in all_exp}
        all_exp = sorted(set(all_exp) | {self.calendar.monthly_expiry(y, m) for y, m in months})
        self._all_expiries = all_exp
        self._qcache: dict = {}

    # -- simulation ------------------------------------------------------------
    def _simulate(self):
        c = self.cfg
        rng = np.random.default_rng(c.seed)
        bars_per_day = int(375 / c.bar_minutes)
        # U-shaped intraday variance profile, normalised to sum 1
        x = np.linspace(0, 1, bars_per_day)
        prof = 1.0 + 1.5 * (x - 0.5) ** 2 * 4
        prof[0] *= 2.0
        prof = prof / prof.sum()
        self._cumprof = np.cumsum(prof)
        regime = 1
        spot = c.spot0
        rows, vix_rows = [], []
        for d in self._days:
            if rng.random() > c.regime_stay_prob:
                regime = int(rng.integers(0, len(c.regime_vols)))
            vol = c.regime_vols[regime] * math.exp(0.1 * rng.standard_normal())
            day_var = vol ** 2 / 252.0
            mu_bar = c.annual_drift / 252.0 / bars_per_day
            gap = math.sqrt(day_var * c.overnight_var_frac) * rng.standard_normal()
            if rng.random() < c.jump_prob_per_day:
                gap += c.jump_size_sd * rng.standard_normal()
            open_px = spot * math.exp(gap)
            sig = np.sqrt(day_var * (1 - c.overnight_var_frac) * prof)
            eps = rng.standard_normal(bars_per_day)
            iv = vol * (1 + c.vrp)
            vix_level = 100 * iv * math.exp(0.05 * rng.standard_normal())
            closes, highs, lows, opens = [], [], [], []
            px = open_px
            or_hi = or_lo = None
            drift_sign = 0
            for i in range(bars_per_day):
                ret = mu_bar - 0.5 * sig[i] ** 2 + sig[i] * eps[i]
                if drift_sign:
                    ret += drift_sign * c.edge_strength * sig[i]
                o = px
                px = px * math.exp(ret)
                wick = abs(sig[i] * rng.standard_normal()) * 0.5
                hi = max(o, px) * (1 + wick)
                lo = min(o, px) * (1 - wick)
                opens.append(o); closes.append(px); highs.append(hi); lows.append(lo)
                if i == c.orb_bars - 1:
                    or_hi, or_lo = max(highs), min(lows)
                elif i >= c.orb_bars and c.edge_strength > 0 and not drift_sign:
                    drift_sign = 1 if px > or_hi else (-1 if px < or_lo else 0)
            spot = px
            ts = list(iter_session_bars(d, c.bar_minutes))
            vol_prof = (prof / prof.max()) * 1e5 * rng.lognormal(0, 0.3, bars_per_day)
            for i, t in enumerate(ts):
                rows.append((d, t, opens[i], highs[i], lows[i], closes[i], vol_prof[i], iv))
            vix_rows.append((d, vix_level))
        bars = pd.DataFrame(rows, columns=["date", "ts", "open", "high", "low", "close", "volume", "atm_iv"])
        vix = pd.DataFrame(vix_rows, columns=["date", "vix"]).set_index("date")["vix"]
        return bars, vix

    # -- MarketData API -------------------------------------------------------
    def trading_days(self) -> list[date]:
        return list(self._days)

    def underlying_bars(self, d: date) -> pd.DataFrame:
        b = self._by_day.get(d)
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"]) if b is None \
            else b[["ts", "open", "high", "low", "close", "volume"]]

    def vix(self, d: date) -> pd.Series:
        b = self._by_day.get(d)
        if b is None:
            return pd.Series(dtype=float)
        return pd.Series(self._vix.loc[d], index=b.ts)

    def expiries(self, d: date) -> list[date]:
        listed = set(self.calendar.expiries_listed_on(d))
        return [e for e in self._all_expiries if e in listed]

    def lot_size(self, d: date, expiry: date | None = None) -> int:
        return self.cfg.lot_size or lot_size_on(d)

    def _strikes(self, d: date) -> np.ndarray:
        c = self.cfg
        atm = round(self._open_spot[d] / c.strike_step) * c.strike_step
        return atm + c.strike_step * np.arange(-c.strikes_each_side, c.strikes_each_side + 1)

    def tau(self, ts: datetime, expiry: date) -> float:
        """Remaining variance-time to expiry in years (trading-time clock)."""
        di, ei = self._day_idx[ts.date()], self._day_idx.get(expiry)
        if ei is None or ei < di:
            return 0.0
        intraday_left = (1 - self.cfg.overnight_var_frac) * (1 - self._cumprof[self._bar_idx[ts]])
        return max((intraday_left + (ei - di)) / 252.0, 0.0)

    def _price_block(self, ts: datetime, expiry: date, strikes: np.ndarray, is_call: np.ndarray):
        c = self.cfg
        s = self._spot_at[ts]
        atm_iv = self._iv_at[ts]
        t = self.tau(ts, expiry)
        fwd = s * math.exp((c.r - c.q) * t)
        m = np.log(strikes / fwd)
        iv = atm_iv * (1 - c.skew * m + c.smile * m * m)
        iv = np.clip(iv, 0.03, 2.0)
        px = bs_price(s, strikes, t, c.r, c.q, iv, is_call)
        half = np.maximum(TICK, 0.004 * px + 0.025) * (1 + 3 * np.abs(m) / max(atm_iv * math.sqrt(max(t, 1e-4)), 1e-3) * 0.05)
        mid = np.maximum(px, TICK)
        bid = np.where(mid - half >= TICK, np.floor((mid - half) / TICK) * TICK, 0.0)
        ask = np.ceil((mid + half) / TICK) * TICK
        oi = 1e6 * np.exp(-np.abs(m) / max(atm_iv * math.sqrt(max(t, 1 / 365)), 1e-3))
        return s, t, iv, bid, ask, mid, oi

    def chain(self, ts: datetime, expiry: date) -> pd.DataFrame:
        d = ts.date()
        if ts not in self._spot_at or expiry < d:
            return pd.DataFrame(columns=CHAIN_COLUMNS)
        k = self._strikes(d)
        strikes = np.concatenate([k, k])
        is_call = np.concatenate([np.ones_like(k, bool), np.zeros_like(k, bool)])
        s, t, iv, bid, ask, mid, oi = self._price_block(ts, expiry, strikes, is_call)
        return pd.DataFrame({
            "expiry": expiry, "strike": strikes,
            "right": np.where(is_call, Right.CALL.value, Right.PUT.value),
            "bid": bid, "ask": ask, "ltp": np.round(mid / TICK) * TICK,
            "volume": oi * 0.3, "oi": oi, "iv": iv * self._cal_scale(ts, expiry, t),
        })

    def _cal_scale(self, ts, expiry, tau) -> float:
        tc = year_fraction(minutes_to_expiry(ts, expiry))
        return math.sqrt(tau / tc) if tc > 0 and tau > 0 else 1.0

    def quote(self, ts: datetime, contract: OptionContract) -> Quote | None:
        if ts not in self._spot_at or contract.expiry < ts.date():
            return None
        key = (ts, contract)
        hit = self._qcache.get(key)
        if hit is not None:
            return hit
        c = self.cfg
        s, atm_iv, k = self._spot_at[ts], self._iv_at[ts], contract.strike
        t = self.tau(ts, contract.expiry)
        fwd = s * math.exp((c.r - c.q) * t)
        m = math.log(k / fwd)
        iv = min(max(atm_iv * (1 - c.skew * m + c.smile * m * m), 0.03), 2.0)
        px = bs_price_scalar(s, k, t, c.r, c.q, iv, contract.right is Right.CALL)
        sd = max(atm_iv * math.sqrt(max(t, 1e-4)), 1e-3)
        half = max(TICK, 0.004 * px + 0.025) * (1 + 0.15 * abs(m) / sd)
        mid = max(px, TICK)
        bid = math.floor((mid - half) / TICK) * TICK if mid - half >= TICK else 0.0
        ask = math.ceil((mid + half) / TICK) * TICK
        oi = 1e6 * math.exp(-abs(m) / max(atm_iv * math.sqrt(max(t, 1 / 365)), 1e-3))
        q = Quote(contract, ts, bid=round(bid, 2), ask=round(ask, 2), ltp=round(round(mid / TICK) * TICK, 2),
                  volume=oi * 0.3, oi=oi, iv=iv * self._cal_scale(ts, contract.expiry, t))
        if len(self._qcache) > 200_000:
            self._qcache.clear()
        self._qcache[key] = q
        return q

    def spot(self, ts: datetime) -> float:
        return self._spot_at[ts]

    def greeks(self, ts: datetime, contract: OptionContract) -> dict[str, float]:
        c = self.cfg
        q = self.quote(ts, contract)
        t = year_fraction(minutes_to_expiry(ts, contract.expiry))
        g = bs_greeks(self._spot_at[ts], contract.strike, t, c.r, c.q, q.iv, contract.right is Right.CALL)
        return {k: float(v) for k, v in g.items()}
