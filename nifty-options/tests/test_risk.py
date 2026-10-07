from datetime import date

from optlab.risk.manager import RiskLimits, RiskManager


def test_trade_rejected_when_one_lot_exceeds_budget():
    rm = RiskManager(RiskLimits(initial_capital=100_000, risk_per_trade_pct=0.01))
    d = rm.check(1_800.0)
    assert not d.approved and d.lots == 0 and "exceeds_budget" in d.reasons[0]


def test_lots_are_floored_never_rounded_up():
    rm = RiskManager(RiskLimits(risk_per_trade_pct=0.02))
    assert rm.check(900.0).lots == 2          # 2000 // 900
    assert rm.check(1_999.0).lots == 1
    assert rm.check(2_001.0).lots == 0


def test_open_risk_cap_and_concurrency():
    rm = RiskManager(RiskLimits(risk_per_trade_pct=0.02, max_open_risk_pct=0.05, max_concurrent_positions=5))
    rm.on_open(4_500.0)
    d = rm.check(900.0)                         # headroom 500 < 900
    assert not d.approved and d.reasons == ("max_open_risk_reached",)


def test_daily_and_weekly_loss_limits():
    rm = RiskManager(RiskLimits())
    rm.on_new_day(date(2025, 3, 3))
    rm.on_open(1000); rm.on_close(1000, -3_000.0)
    assert rm.can_open() == (False, "daily_loss_limit")
    rm.on_new_day(date(2025, 3, 4))
    assert rm.can_open() == (True, None)
    rm.on_open(1000); rm.on_close(1000, -2_900.0)    # week total -5,900 < 6% of 100k
    assert rm.can_open()[0]
    rm.on_open(1000); rm.on_close(1000, -200.0)       # week -6,100
    assert rm.can_open() == (False, "daily_loss_limit") or rm.can_open() == (False, "weekly_loss_limit")
    rm.on_new_day(date(2025, 3, 5))
    assert rm.can_open() == (False, "weekly_loss_limit")
    rm.on_new_day(date(2025, 3, 10))                  # new ISO week
    assert rm.can_open() == (True, None)


def test_budget_scales_with_equity():
    rm = RiskManager(RiskLimits())
    rm.on_open(0); rm.on_close(0, -10_000.0)
    assert rm.trade_budget() == 900.0
