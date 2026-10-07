import math

import numpy as np
import pandas as pd
import pytest

from optlab.backtest.engine import Backtester, CoreConfig
from optlab.backtest.metrics import full_metrics, trade_metrics
from optlab.execution.costs import ZERO_COSTS
from optlab.execution.fills import FillModel, FillModelName
from optlab.risk.manager import RiskLimits
from optlab.strategies.base import Strategy, StrategyConfig
from optlab.strategies.exits import ExitConfig
from optlab.strategies.structures import StructureSpec


def _cfg(kind="debit_spread", **kw):
    return StrategyConfig(name="t", structure=StructureSpec(kind=kind, width_points=100), exits=ExitConfig(**kw))


@pytest.fixture(scope="module")
def run_small(md_small):
    bt = Backtester(md_small)
    return bt.run(Strategy(_cfg(), md_small))


def test_pnl_reconciles_leg_by_leg(run_small):
    t = run_small.trades
    assert len(t) > 20
    for _, r in t.iterrows():
        gross_pts = sum(q * (x - e) for q, x, e in zip(r.ratios, r.exit_prices, r.entry_prices))
        assert r.gross_pnl == pytest.approx(gross_pts * r.lot_size * r.lots)
        assert r.net_pnl == pytest.approx(r.gross_pnl - r.fees)
        assert r.fees == pytest.approx(r.fees_entry + r.fees_exit)
        assert r.net_pnl >= -r.account_risk - 1e-6 - r.slippage_rupees  # never lose more than max risk + exit slippage
        assert r.r_multiple == pytest.approx(r.net_pnl / r.account_risk)


def test_no_lookahead_timing(run_small):
    t = run_small.trades
    assert (pd.to_datetime(t.entry_ts) > pd.to_datetime(t.signal_ts)).all()      # 1-bar fill delay
    assert (pd.to_datetime(t.exit_ts) > pd.to_datetime(t.entry_ts)).all()
    assert (pd.to_datetime(t.exit_ts).dt.date == pd.to_datetime(t.entry_ts).dt.date).all()   # intraday config
    assert (pd.to_datetime(t.exit_ts).dt.time <= pd.Timestamp("15:30").time()).all()


def test_costs_and_fills_only_reduce_pnl(md_small):
    s = Strategy(_cfg(), md_small)
    ideal = Backtester(md_small, FillModel(FillModelName.OPTIMISTIC, slippage_ticks=0), ZERO_COSTS).run(s).trades
    real = Backtester(md_small).run(s).trades
    pess = Backtester(md_small, FillModel(FillModelName.PESSIMISTIC)).run(s).trades
    assert len(ideal) == len(real) == len(pess)
    assert ideal.net_pnl.sum() > real.net_pnl.sum() > pess.net_pnl.sum()
    # with zero costs + mid fills, net equals theoretical (mid-to-mid) up to tick rounding
    assert np.allclose(ideal.net_pnl, ideal.theoretical_pnl, atol=0.05 * 2 * 75 * 2)


def test_portfolio_mode_rejects_oversized_trades(md_small):
    bt = Backtester(md_small, core_cfg=CoreConfig(mode="portfolio"))
    r = bt.run(Strategy(_cfg(kind="long_option"), md_small))
    # with Rs 1,000 budget and NIFTY lot sizes, ATM long options never fit
    assert len(r.trades) == 0
    assert (r.rejections.stage == "risk").sum() > 0
    assert any("exceeds_budget" in x for rs in r.rejections.reasons for x in rs)


def test_portfolio_mode_respects_limits_when_feasible(md_small):
    lim = RiskLimits(risk_per_trade_pct=0.05, max_open_risk_pct=0.05)
    r = Backtester(md_small, limits=lim, core_cfg=CoreConfig(mode="portfolio")).run(
        Strategy(_cfg(stop_loss_pct=0.5), md_small))
    assert len(r.trades) > 0
    assert (r.trades.account_risk <= 0.05 * r.trades.equity_before + 1e-6).all()


def test_null_control_has_no_edge(md_small):
    """Driftless synthetic market: expectancy after costs must not be significantly positive."""
    m = trade_metrics(Backtester(md_small).run(Strategy(_cfg(), md_small)).trades)
    assert m["expectancy_r"] < 0.05
    assert m.get("expectancy_tstat", 0) < 2.0


def test_positive_control_is_detected(md_edge):
    m = trade_metrics(Backtester(md_edge).run(Strategy(_cfg(), md_edge)).trades)
    assert m["expectancy_r"] > 0.05 and m["expectancy_tstat"] > 2.0


def test_metrics_expectancy_formula():
    t = pd.DataFrame({"net_pnl": [300.0, -100.0, -100.0, 500.0], "r_multiple": [3, -1, -1, 5]})
    m = trade_metrics(t)
    assert m["win_rate"] == 0.5
    assert m["expectancy"] == pytest.approx(0.5 * 400 - 0.5 * 100) == m["expectancy_check_mean"]
    assert m["profit_factor"] == 4.0 and m["payoff_ratio"] == 4.0
