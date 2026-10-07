import math
from datetime import date

import pytest

from optlab.core import instruments as ins
from optlab.core.instruments import Leg, OptionContract, Right, Structure, risk_profile

E = date(2025, 1, 30)


def test_bull_call_spread_exact():
    k1, k2, c1, c2 = 23000, 23200, 120.0, 45.0
    st = ins.bull_call_spread("NIFTY", E, k1, k2)
    rp = risk_profile(st, [c1, c2])
    debit = c1 - c2
    assert rp.net_premium == debit == 75.0
    assert rp.max_loss == debit
    assert rp.max_gain == (k2 - k1) - debit == 125.0
    assert rp.breakevens == (k1 + debit,)
    assert ins.pnl_at_expiry(st, [c1, c2], 22000) == -debit
    assert ins.pnl_at_expiry(st, [c1, c2], 24000) == (k2 - k1) - debit
    assert ins.pnl_at_expiry(st, [c1, c2], k1 + debit) == 0.0


def test_bear_put_spread_exact():
    k_long, k_short, p1, p2 = 23000, 22800, 110.0, 50.0
    st = ins.bear_put_spread("NIFTY", E, k_long, k_short)
    rp = risk_profile(st, [p1, p2])
    debit = p1 - p2
    assert rp.max_loss == debit == 60.0
    assert rp.max_gain == (k_long - k_short) - debit == 140.0
    assert rp.breakevens == (k_long - debit,)


def test_long_call_unlimited_gain_and_long_put_bounded():
    rp = risk_profile(ins.long_call("NIFTY", E, 23000), [100.0])
    assert rp.max_loss == 100.0 and math.isinf(rp.max_gain) and rp.breakevens == (23100.0,)
    rp = risk_profile(ins.long_put("NIFTY", E, 23000), [100.0])
    assert rp.max_loss == 100.0 and rp.max_gain == 22900.0 and rp.breakevens == (22900.0,)


def test_straddle_and_strangle():
    rp = risk_profile(ins.long_straddle("NIFTY", E, 23000), [100.0, 90.0])
    assert rp.max_loss == 190.0 and math.isinf(rp.max_gain)
    assert rp.breakevens == (22810.0, 23190.0)
    rp = risk_profile(ins.long_strangle("NIFTY", E, 22800, 23200), [40.0, 35.0])
    assert rp.max_loss == 75.0 and rp.breakevens == (22725.0, 23275.0)


def test_butterfly_and_iron_condor():
    rp = risk_profile(ins.call_butterfly("NIFTY", E, 22900, 23000, 23100), [150.0, 90.0, 45.0])
    debit = 150 - 180 + 45
    assert rp.max_loss == debit == 15.0
    assert rp.max_gain == 100 - debit
    assert rp.breakevens == (22900 + debit, 23100 - debit)
    ic = ins.iron_condor("NIFTY", E, 22700, 22800, 23200, 23300)
    rp = risk_profile(ic, [10.0, 20.0, 22.0, 9.0])
    credit = -(10 - 20 - 22 + 9)
    assert rp.net_premium == -credit
    assert rp.max_gain == credit == 23.0
    assert rp.max_loss == 100 - credit
    assert rp.breakevens == (22800 - credit, 23200 + credit)


def test_naked_short_call_is_unbounded():
    c = OptionContract("NIFTY", E, 23000.0, Right.CALL)
    rp = risk_profile(Structure("naked_short_call", (Leg(c, -1),)), [100.0])
    assert math.isinf(rp.max_loss) and not rp.defined_risk


def test_invalid_structures():
    with pytest.raises(ValueError):
        ins.bull_call_spread("NIFTY", E, 23200, 23000)
    with pytest.raises(ValueError):
        risk_profile(ins.long_call("NIFTY", E, 23000), [1.0, 2.0])
