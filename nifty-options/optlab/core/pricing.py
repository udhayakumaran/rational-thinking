"""Black-Scholes-Merton pricing, greeks and implied volatility.

Used for: (a) computing IV/greeks from *observed* option prices, and
(b) generating clearly-labelled SYNTHETIC data. Never used to replace real
historical option prices in a real-data backtest.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm

MIN_T = 1e-6  # years; avoids division by zero at expiry


def _d1_d2(s, k, t, r, q, sigma):
    t = np.maximum(t, MIN_T)
    sig = np.maximum(sigma, 1e-6)
    vs = sig * np.sqrt(t)
    d1 = (np.log(s / k) + (r - q + 0.5 * sig * sig) * t) / vs
    return d1, d1 - vs, t


def bs_price(s, k, t, r, q, sigma, is_call):
    """Vectorised BSM price. ``is_call`` may be bool or array of bools."""
    s, k, t, sigma = (np.asarray(x, dtype=float) for x in (s, k, t, sigma))
    is_call = np.asarray(is_call, dtype=bool)
    d1, d2, tt = _d1_d2(s, k, t, r, q, sigma)
    df_r, df_q = np.exp(-r * tt), np.exp(-q * tt)
    call = s * df_q * norm.cdf(d1) - k * df_r * norm.cdf(d2)
    put = k * df_r * norm.cdf(-d2) - s * df_q * norm.cdf(-d1)
    px = np.where(is_call, call, put)
    intrinsic = np.where(is_call, np.maximum(s - k, 0), np.maximum(k - s, 0))
    return np.where(t <= MIN_T, intrinsic, px)


def bs_greeks(s, k, t, r, q, sigma, is_call) -> dict[str, np.ndarray]:
    """Delta, gamma, theta (per calendar day), vega (per 1 vol point)."""
    s, k, t, sigma = (np.asarray(x, dtype=float) for x in (s, k, t, sigma))
    is_call = np.asarray(is_call, dtype=bool)
    d1, d2, tt = _d1_d2(s, k, t, r, q, sigma)
    df_r, df_q = np.exp(-r * tt), np.exp(-q * tt)
    pdf = norm.pdf(d1)
    sq = np.sqrt(tt)
    delta = np.where(is_call, df_q * norm.cdf(d1), df_q * (norm.cdf(d1) - 1))
    gamma = df_q * pdf / (s * np.maximum(sigma, 1e-6) * sq)
    common = -s * df_q * pdf * sigma / (2 * sq)
    theta_c = common - r * k * df_r * norm.cdf(d2) + q * s * df_q * norm.cdf(d1)
    theta_p = common + r * k * df_r * norm.cdf(-d2) - q * s * df_q * norm.cdf(-d1)
    theta = np.where(is_call, theta_c, theta_p) / 365.0
    vega = s * df_q * pdf * sq / 100.0
    return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega}


def implied_vol(price: float, s: float, k: float, t: float, r: float, q: float, is_call: bool,
                lo: float = 1e-4, hi: float = 5.0) -> float:
    """Implied volatility via Brent's method; NaN if price violates no-arb bounds."""
    if not (price > 0 and s > 0 and k > 0) or t <= MIN_T:
        return math.nan
    df_r, df_q = math.exp(-r * t), math.exp(-q * t)
    lower = max(s * df_q - k * df_r, 0.0) if is_call else max(k * df_r - s * df_q, 0.0)
    upper = s * df_q if is_call else k * df_r
    if not (lower - 1e-9 <= price < upper):
        return math.nan

    def f(sig: float) -> float:
        return float(bs_price(s, k, t, r, q, sig, is_call)) - price

    try:
        if f(lo) > 0:
            return math.nan   # price at/below the ~zero-vol value: IV not identifiable
        if f(hi) < 0:
            return math.nan
        return brentq(f, lo, hi, xtol=1e-7, maxiter=200)
    except (ValueError, RuntimeError):
        return math.nan


def _ncdf(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def bs_price_scalar(s: float, k: float, t: float, r: float, q: float, sigma: float, is_call: bool) -> float:
    """Fast scalar BSM (same maths as ``bs_price``) for per-quote use in loops."""
    if t <= MIN_T or sigma <= 0:
        return max(s - k, 0.0) if is_call else max(k - s, 0.0)
    vs = sigma * math.sqrt(t)
    d1 = (math.log(s / k) + (r - q + 0.5 * sigma * sigma) * t) / vs
    d2 = d1 - vs
    if is_call:
        return s * math.exp(-q * t) * _ncdf(d1) - k * math.exp(-r * t) * _ncdf(d2)
    return k * math.exp(-r * t) * _ncdf(-d2) - s * math.exp(-q * t) * _ncdf(-d1)


def year_fraction(minutes_to_expiry: float) -> float:
    """Calendar-time year fraction from minutes to expiry."""
    return max(minutes_to_expiry, 0.0) / (365.0 * 24 * 60)
