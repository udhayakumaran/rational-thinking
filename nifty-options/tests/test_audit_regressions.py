"""Regression tests for the independent backtest audit (missing data, fills, gates)."""
from datetime import date, datetime, time

import numpy as np
import pandas as pd
import pytest

from optlab.backtest.engine import Backtester
from optlab.core.instruments import OptionContract, Right
from optlab.core.market import Quote
from optlab.data.interfaces import BAR_COLUMNS
from optlab.execution.costs import Side
from optlab.execution.fills import FillModel, FillModelName
from optlab.research.montecarlo import monte_carlo_lots
from optlab.strategies.base import Strategy, StrategyConfig
from optlab.strategies.exits import ExitConfig, ExitState, check_exit
from optlab.strategies.structures import StructureSpec


class Holey:
    """Wraps a MarketData and hides chosen underlying days / quote timestamps."""
    def __init__(self, md, drop_days=(), drop_quote_ts=(), drop_quotes_after: time | None = None):
        self._md, self.drop_days, self.drop_ts, self.after = md, set(drop_days), set(drop_quote_ts), drop_quotes_after

    def __getattr__(self, k):
        return getattr(self._md, k)

    def underlying_bars(self, d):
        return pd.DataFrame(columns=BAR_COLUMNS) if d in self.drop_days else self._md.underlying_bars(d)

    def quote(self, ts, c):
        if ts in self.drop_ts or (self.after and ts.time() > self.after):
            return None
        return self._md.quote(ts, c)


def _cfg(**exits):
    return StrategyConfig(name="a", structure=StructureSpec(kind="debit_spread", width_points=100, min_dte=1),
                          exits=ExitConfig(**exits))


def test_position_never_vanishes_when_expiry_day_missing(md_small):
    cfg = _cfg(stop_loss_pct=None, eod_exit_time=None, max_hold_days=5)
    base = Backtester(md_small).run(Strategy(cfg, md_small))
    held = base.trades[base.trades.exit_reason.isin(["pre_expiry_exit", "expiry_settlement"])]
    exp_day = pd.Timestamp(held.expiry.iloc[0]).date()
    holey = Holey(md_small, drop_days={exp_day})
    r = Backtester(holey).run(Strategy(cfg, holey))
    flagged = r.trades[r.trades.exit_flags.map(lambda f: "proxy_settlement_spot" in f)]
    assert len(flagged) >= 1                        # settled with a flag instead of disappearing
    assert len(r.trades) >= len(base.trades) - 3     # strategy keeps trading afterwards


def test_decided_exit_is_retried_not_cancelled(md_small):
    cfg = _cfg(stop_loss_pct=0.3)
    base = Backtester(md_small).run(Strategy(cfg, md_small))
    stop = base.trades[base.trades.exit_reason == "stop_loss"].iloc[0]
    holey = Holey(md_small, drop_quote_ts={pd.Timestamp(stop.exit_ts).to_pydatetime()})
    r = Backtester(holey).run(Strategy(cfg, holey))
    same = r.trades[r.trades.entry_ts == stop.entry_ts].iloc[0]
    assert same.exit_reason == "stop_loss"
    assert pd.Timestamp(same.exit_ts) > pd.Timestamp(stop.exit_ts)   # filled on a later bar


def test_intraday_trade_never_carried_overnight_when_quotes_missing(md_small):
    holey = Holey(md_small, drop_quotes_after=time(15, 10))
    r = Backtester(holey).run(Strategy(_cfg(), holey))
    assert len(r.trades)
    assert (pd.to_datetime(r.trades.exit_ts).dt.date == pd.to_datetime(r.trades.entry_ts).dt.date).all()
    forced = r.trades[r.trades.exit_flags.map(len) > 0]
    assert len(forced) > 0


def test_one_sided_quotes_fill_only_at_observed_touch():
    c = OptionContract("NIFTY", date(2025, 3, 6), 23000.0, Right.CALL)
    q = Quote(c, None, bid=0.0, ask=1.0, ltp=3.0)
    fm = FillModel(FillModelName.REALISTIC)
    with pytest.raises(ValueError):
        fm.fill(Side.SELL, q)                        # no bid: cannot sell, never at stale LTP
    assert fm.fill(Side.BUY, q).price == 1.05
    assert fm.mid(q) == 1.0


def test_credit_structure_stops_fire():
    t0 = datetime(2025, 3, 3, 10)
    st = ExitState(entry_debit=-20.0, max_profit=20.0, direction_sign=0, entry_ts=t0, features={}, max_loss=80.0)
    cfg = ExitConfig(stop_loss_pct=0.5, target_pct_max_profit=0.5)
    assert check_exit(cfg, st, t0, -61.0, 0, None, False, False) == "stop_loss"      # lost 41 > 40
    assert check_exit(cfg, st, t0, -9.0, 0, None, False, False) == "target_pct_max_profit"
    assert check_exit(cfg, st, t0, -25.0, 0, None, False, False) is None


def test_lot_monte_carlo_skips_untradable_trades():
    r = np.array([1.0, -1.0] * 50)
    mc = monte_carlo_lots(r, np.full(100, 2_364.0), risk_pct=0.01, n_trades=200, n_sims=200)
    assert mc.share_trades_taken == 0.0 and mc.median_final == 100_000
    mc2 = monte_carlo_lots(r, np.full(100, 900.0), risk_pct=0.01, n_trades=200, n_sims=200)
    assert mc2.share_trades_taken > 0.9
