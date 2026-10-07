from datetime import date

from optlab.core.calendar import TradingCalendar, lot_size_on


def test_weekly_expiry_weekday_switch():
    cal = TradingCalendar()
    assert all(e.weekday() == 3 for e in cal.weekly_expiries(date(2025, 7, 1), date(2025, 8, 28)))
    assert all(e.weekday() == 1 for e in cal.weekly_expiries(date(2025, 9, 1), date(2025, 10, 31)))


def test_holiday_moves_expiry_back():
    cal = TradingCalendar(holidays={date(2025, 9, 2)})
    assert date(2025, 9, 1) in cal.weekly_expiries(date(2025, 9, 1), date(2025, 9, 5))


def test_monthly_expiry_last_weekday():
    cal = TradingCalendar()
    assert cal.monthly_expiry(2025, 6) == date(2025, 6, 26)     # last Thursday
    assert cal.monthly_expiry(2025, 10) == date(2025, 10, 28)   # last Tuesday
    assert cal.is_monthly_expiry(date(2025, 10, 28))


def test_dte_and_trading_days():
    cal = TradingCalendar()
    assert cal.trading_days_to_expiry(date(2025, 10, 6), date(2025, 10, 7)) == 1
    assert cal.trading_days_to_expiry(date(2025, 10, 7), date(2025, 10, 7)) == 0
    assert cal.trading_days_to_expiry(date(2025, 10, 3), date(2025, 10, 7)) == 2   # Fri -> Tue


def test_lot_size_schedule():
    assert lot_size_on(date(2025, 6, 1)) == 75
    assert lot_size_on(date(2026, 3, 1)) == 65
