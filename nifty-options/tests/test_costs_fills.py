from datetime import date

import pytest

from optlab.core.instruments import OptionContract, Right
from optlab.core.market import Quote
from optlab.execution.costs import CostModel, Side
from optlab.execution.fills import FillModel, FillModelName

D = date(2025, 3, 3)
C = OptionContract("NIFTY", date(2025, 3, 6), 22500.0, Right.CALL)


def test_buy_order_costs_by_hand():
    cm = CostModel()
    b = cm.order_costs(Side.BUY, 100.0, 75, D)       # turnover 7,500
    assert b.brokerage == 20.0
    assert b.exchange == pytest.approx(7500 * 0.0003503)
    assert b.sebi == pytest.approx(7500 * 1e-6)
    assert b.stamp == pytest.approx(7500 * 3e-5)
    assert b.stt == 0.0
    assert b.gst == pytest.approx(0.18 * (20 + 7500 * 0.0003503 + 7500 * 1e-6))


def test_dated_exchange_charge():
    cm = CostModel()
    assert cm.exchange_rate(date(2024, 9, 30)) == 0.000495 and cm.exchange_rate(D) == 0.0003503


def test_sell_order_stt_schedule():
    cm = CostModel()
    assert cm.order_costs(Side.SELL, 100.0, 75, date(2015, 1, 5)).stt == pytest.approx(7500 * 0.00017)
    assert cm.order_costs(Side.SELL, 100.0, 75, date(2022, 1, 5)).stt == pytest.approx(7500 * 0.0005)
    assert cm.order_costs(Side.SELL, 100.0, 75, date(2024, 9, 30)).stt == pytest.approx(7500 * 0.000625)
    assert cm.order_costs(Side.SELL, 100.0, 75, date(2026, 5, 4)).stt == pytest.approx(7500 * 0.0015)
    assert cm.order_costs(Side.SELL, 100.0, 75, D).stt == pytest.approx(7500 * 0.001)
    assert cm.order_costs(Side.SELL, 100.0, 75, D).stamp == 0.0


def test_exercise_stt_only_on_itm_longs():
    cm = CostModel()
    assert cm.exercise_costs(50.0, 75, D).stt == pytest.approx(50 * 75 * 0.00125)
    assert cm.exercise_costs(0.0, 75, D).total == 0.0


def test_fill_models():
    q = Quote(C, None, bid=100.0, ask=102.0, ltp=101.0)
    opt = FillModel(FillModelName.OPTIMISTIC, slippage_ticks=0)
    real = FillModel(FillModelName.REALISTIC, realistic_spread_fraction=0.5, slippage_ticks=1)
    pess = FillModel(FillModelName.PESSIMISTIC, slippage_ticks=1)
    assert opt.fill(Side.BUY, q).price == 101.0 and opt.fill(Side.SELL, q).price == 101.0
    assert real.fill(Side.BUY, q).price == 101.55      # 101 + 0.5*1 + 0.05
    assert real.fill(Side.SELL, q).price == 100.45
    assert pess.fill(Side.BUY, q).price == 102.05
    assert pess.fill(Side.SELL, q).price == 99.95
    assert pess.fill(Side.BUY, q).slippage_points == pytest.approx(1.05)


def test_rounding_against_trader_and_estimated_spread():
    q = Quote(C, None, bid=10.0, ask=10.13, ltp=10.05)
    f = FillModel(FillModelName.OPTIMISTIC, slippage_ticks=0)
    assert f.fill(Side.BUY, q).price == 10.10   # mid 10.065 rounds up
    assert f.fill(Side.SELL, q).price == 10.05  # rounds down
    ltp_only = Quote(C, None, ltp=100.0)
    fl = FillModel(FillModelName.PESSIMISTIC, slippage_ticks=0).fill(Side.BUY, ltp_only)
    assert fl.spread_estimated and fl.price == 100.5
