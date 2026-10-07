from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from optlab.core.instruments import Direction
from optlab.strategies.exits import ExitConfig, ExitState, check_exit
from optlab.strategies.indicators import ema, roc, rsi, vwap
from optlab.strategies.signals import ORBConfig, OpeningRangeBreakout
from optlab.strategies.structures import StructureBuilder, StructureSpec


def _ts(md):
    d = md.trading_days()[10]
    return d, md.underlying_bars(d)


def test_structure_strike_selection(md_small):
    d, bars = _ts(md_small)
    ts = bars.ts.iloc[10]
    spot = bars.close.iloc[10]
    b = StructureBuilder(StructureSpec(kind="debit_spread", long_offset_steps=1, width_points=200), md_small)
    bull = b.build(ts, Direction.BULLISH, spot)
    atm = bull.atm_strike
    assert abs(atm - spot) <= 25
    assert [l.contract.strike for l in bull.structure.legs] == [atm + 50, atm + 250]
    bear = b.build(ts, Direction.BEARISH, spot)
    assert [l.contract.strike for l in bear.structure.legs] == [atm - 50, atm - 250]
    assert {l.contract.right.value for l in bear.structure.legs} == {"PE"}
    itm = StructureBuilder(StructureSpec(kind="debit_spread", long_offset_steps=-2, width_points=100), md_small)
    assert itm.build(ts, Direction.BULLISH, spot).structure.legs[0].contract.strike == atm - 100


def test_expiry_selection_respects_min_dte(md_small):
    d, bars = _ts(md_small)
    b0 = StructureBuilder(StructureSpec(min_dte=0), md_small)
    b2 = StructureBuilder(StructureSpec(min_dte=2), md_small)
    e0, dte0 = b0.select_expiry(d)
    e2, dte2 = b2.select_expiry(d)
    assert dte2 >= 2 and e2 >= e0


def test_exit_rules_priority():
    t0 = datetime(2025, 3, 3, 10, 0)
    cfg = ExitConfig(stop_loss_pct=0.5, target_pct_max_profit=0.5, eod_exit_time="15:15")
    st = ExitState(entry_debit=40.0, max_profit=60.0, direction_sign=1, entry_ts=t0, features={})
    assert check_exit(cfg, st, t0, 20.0, 0, None, False, False) == "stop_loss"
    assert check_exit(cfg, st, t0, 70.0, 0, None, False, False) == "target_pct_max_profit"
    assert check_exit(cfg, st, t0, 50.0, 0, None, False, False) is None
    assert check_exit(cfg, st, t0.replace(hour=15, minute=15), 50.0, 0, None, False, False) == "eod_exit"
    inv = ExitConfig(stop_loss_pct=None, underlying_invalidation="or_mid")
    st2 = ExitState(40.0, 60.0, 1, t0, {"or_high": 110.0, "or_low": 90.0})
    assert check_exit(inv, st2, t0, 40.0, 99.0, None, False, False) == "underlying_invalidation"
    assert check_exit(inv, st2, t0, 40.0, 101.0, None, False, False) is None
    exp = ExitConfig(stop_loss_pct=None, eod_exit_time=None, max_hold_days=3)
    assert check_exit(exp, ExitState(40, 60, 1, t0, {}), t0.replace(hour=15), 40, 0, None, True, False) == "pre_expiry_exit"


def test_indicators_and_signals_are_causal(md_small):
    """Truncating future bars must not change any past value (no look-ahead)."""
    for d in md_small.trading_days()[5:25]:
        bars = md_small.underlying_bars(d).reset_index(drop=True)
        full_vw = vwap(bars)
        full_rsi = rsi(bars.close, 14)
        sig = OpeningRangeBreakout(ORBConfig(), bar_minutes=5)
        full_sigs = {(e.ts, e.direction) for e in sig.compute_day(bars, None)}
        for cut in (5, 20, 40):
            part = bars.iloc[:cut]
            assert np.allclose(vwap(part).to_numpy(), full_vw.iloc[:cut].to_numpy(), equal_nan=True)
            assert np.allclose(rsi(part.close, 14).to_numpy(), full_rsi.iloc[:cut].to_numpy(), equal_nan=True)
            part_sigs = {(e.ts, e.direction) for e in sig.compute_day(part, None)}
            assert part_sigs == {s for s in full_sigs if s[0] <= part.ts.iloc[-1]}


def test_orb_signal_conditions():
    t0 = datetime(2025, 3, 3, 9, 20)
    closes = [100, 101, 100.5, 100.8, 102.0, 103.0, 103.5] + [103.0] * 10
    rows = [{"ts": t0 + timedelta(minutes=5 * i), "open": c, "high": c + 0.2, "low": c - 0.2, "close": c, "volume": 1.0}
            for i, c in enumerate(closes)]
    bars = pd.DataFrame(rows)
    ev = OpeningRangeBreakout(ORBConfig(entry_start="09:15"), 5).compute_day(bars, None)
    assert len(ev) == 1 and ev[0].direction is Direction.BULLISH and ev[0].ts == rows[4]["ts"]
