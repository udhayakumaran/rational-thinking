from datetime import date

import pandas as pd
from sqlalchemy import func, select

from optlab.backtest.engine import Backtester, CoreConfig
from optlab.db.models import AccountEquity, PaperFill, PaperOrder, PaperPosition, PaperTrade, SignalRow
from optlab.db.session import session_factory
from optlab.paper.compare import compare
from optlab.paper.engine import PaperEngine
from optlab.risk.manager import RiskLimits
from optlab.strategies.base import Strategy, StrategyConfig
from optlab.strategies.exits import ExitConfig
from optlab.strategies.structures import StructureSpec

CFG = StrategyConfig(name="p", structure=StructureSpec(kind="debit_spread", width_points=50), exits=ExitConfig())
LIM = RiskLimits(risk_per_trade_pct=0.03)


def test_paper_replay_matches_backtest_and_persists(md_small, tmp_path):
    days = md_small.trading_days()
    start, end = days[0], days[30]
    sessions = session_factory(f"sqlite:///{tmp_path/'p.db'}")
    eng = PaperEngine(md_small, [CFG], sessions, limits=LIM, report_dir=tmp_path / "reports")
    eng.run_replay(start, end)
    paper = eng.trades_df()
    bt = Backtester(md_small, limits=LIM, core_cfg=CoreConfig(mode="portfolio")).run(Strategy(CFG, md_small), start, end)
    assert len(paper) == len(bt.trades) > 0
    cols = ["entry_ts", "exit_ts", "structure", "lots", "net_pnl", "exit_reason"]
    pd.testing.assert_frame_equal(paper[cols].reset_index(drop=True), bt.trades[cols].reset_index(drop=True))
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(PaperTrade)) == len(paper)
        n_legs = int(paper.ratios.map(len).sum())
        assert s.scalar(select(func.count()).select_from(PaperOrder)) == 2 * n_legs
        assert s.scalar(select(func.count()).select_from(PaperFill)) == 2 * n_legs
        assert s.scalar(select(func.count()).select_from(SignalRow)) >= len(paper)
        assert s.scalar(select(func.count()).select_from(AccountEquity)) > 0
        assert s.scalar(select(func.count()).select_from(PaperPosition).where(PaperPosition.status == "OPEN")) == 0
    reports = list((tmp_path / "reports").glob("*.md"))
    assert len(reports) == 31
    c = compare(bt.trades, paper)
    assert c["paper_consistency"] > 0.9
