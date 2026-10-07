"""NSE trading-calendar rules for NIFTY options.

Precedence when real data is available: the *data* (instrument master /
bhavcopy) is authoritative for expiry dates and lot sizes. The rules here are
used for synthetic data, sanity checks against the data, and live paper
trading where the instrument master is not yet loaded.

Rule history encoded below (verify against NSE circulars before relying on it;
entries marked UNVERIFIED are best-effort recollection):
  * NIFTY weekly options: Thursday expiry from 2019-02 onwards.
  * From 2025-09-01 NSE moved NIFTY weekly and monthly expiries to Tuesday.
  * Monthly expiry = last expiry weekday of the month.
  * An expiry falling on a holiday moves to the previous trading day.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Iterable

SESSION_OPEN = time(9, 15)
SESSION_CLOSE = time(15, 30)
TUESDAY_SWITCH = date(2025, 9, 1)

# NSE applies lot sizes per CONTRACT SERIES, so the schedule is keyed by the
# contract's EXPIRY: (first expiry date using the lot size, lot size).
# Reviewed 2026-10 against NSE circulars/broker bulletins. The real data's
# instrument master always wins over this table.
NIFTY_LOT_SIZE_SCHEDULE: list[tuple[date, int]] = [
    (date(2000, 1, 1), 25),
    (date(2015, 11, 1), 75),   # medium-low confidence on the exact switch
    (date(2021, 7, 1), 50),    # contracts expiring Jul-2021 onward (circular 2021-03-31)
    (date(2024, 5, 1), 25),    # effective 2024-04-26; first weekly expiring 2024-05-02
    (date(2024, 12, 1), 75),   # new series listed from 2024-11-20. CAVEAT: the Dec-2024 monthly
                               # listed earlier kept 25 until expiry - take lots from data
    (date(2025, 12, 31), 65),  # weeklies from 2026-01-06; monthlies 75 through 2025-12-30
]


def lot_size_for_expiry(expiry: date, schedule: list[tuple[date, int]] = NIFTY_LOT_SIZE_SCHEDULE) -> int:
    idx = bisect.bisect_right([s[0] for s in schedule], expiry) - 1
    if idx < 0:
        raise ValueError(f"no lot size defined for expiry {expiry}")
    return schedule[idx][1]


def lot_size_on(d: date, schedule: list[tuple[date, int]] = NIFTY_LOT_SIZE_SCHEDULE) -> int:
    """Approximation when the contract expiry is unknown: the series expiring on/after ``d``."""
    return lot_size_for_expiry(d, schedule)


@dataclass
class TradingCalendar:
    holidays: set[date] = field(default_factory=set)

    def is_trading_day(self, d: date) -> bool:
        return d.weekday() < 5 and d not in self.holidays

    def trading_days(self, start: date, end: date) -> list[date]:
        out, d = [], start
        while d <= end:
            if self.is_trading_day(d):
                out.append(d)
            d += timedelta(days=1)
        return out

    def previous_trading_day(self, d: date) -> date:
        d -= timedelta(days=1)
        while not self.is_trading_day(d):
            d -= timedelta(days=1)
        return d

    def adjust_for_holiday(self, d: date) -> date:
        return d if self.is_trading_day(d) else self.previous_trading_day(d)

    # -- expiry rules -------------------------------------------------------
    @staticmethod
    def expiry_weekday(d: date) -> int:
        return 1 if d >= TUESDAY_SWITCH else 3  # Tue=1, Thu=3

    def weekly_expiries(self, start: date, end: date) -> list[date]:
        out: set[date] = set()
        d = start
        while d <= end + timedelta(days=7):   # +7: a holiday shift can pull an expiry back into range
            if d.weekday() == self.expiry_weekday(d):
                e = self.adjust_for_holiday(d)
                if start <= e <= end:
                    out.add(e)
            d += timedelta(days=1)
        return sorted(out)

    def monthly_expiry(self, year: int, month: int) -> date:
        nxt = date(year + (month == 12), month % 12 + 1, 1)
        d = nxt - timedelta(days=1)
        while d.weekday() != self.expiry_weekday(d):
            d -= timedelta(days=1)
        return self.adjust_for_holiday(d)

    def is_monthly_expiry(self, e: date) -> bool:
        return e == self.monthly_expiry(e.year, e.month)

    def expiries_listed_on(self, d: date, n_weekly: int = 4, n_monthly: int = 3) -> list[date]:
        weeklies = [e for e in self.weekly_expiries(d, d + timedelta(days=7 * (n_weekly + 1))) if e >= d][:n_weekly]
        monthlies, y, m = [], d.year, d.month
        while len(monthlies) < n_monthly:
            e = self.monthly_expiry(y, m)
            if e >= d:
                monthlies.append(e)
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        return sorted(set(weeklies) | set(monthlies))

    def trading_days_to_expiry(self, d: date, expiry: date) -> int:
        """0 on expiry day itself."""
        return max(len(self.trading_days(d, expiry)) - 1, 0)


def minutes_to_expiry(ts: datetime, expiry: date) -> float:
    """Calendar minutes from ``ts`` to expiry-day session close."""
    exp_dt = datetime.combine(expiry, SESSION_CLOSE)
    return max((exp_dt - ts.replace(tzinfo=None)).total_seconds() / 60.0, 0.0)


def iter_session_bars(d: date, bar_minutes: int) -> Iterable[datetime]:
    """Bar *end* timestamps for a regular session (09:15 + bar .. 15:30)."""
    t = datetime.combine(d, SESSION_OPEN) + timedelta(minutes=bar_minutes)
    end = datetime.combine(d, SESSION_CLOSE)
    while t <= end:
        yield t
        t += timedelta(minutes=bar_minutes)
