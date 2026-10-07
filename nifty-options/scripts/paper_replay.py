#!/usr/bin/env python3
"""Rehearse the paper-trading engine by replaying historical (or synthetic) data bar by bar.

    python scripts/paper_replay.py --strategy-from reports/VAL-002/summary.json --variant B_atm_to_otm100 \
        --days 20 [--synthetic-edge 0.04]
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from optlab.config import db_url, load_config  # noqa: E402
from optlab.data.synthetic import SyntheticConfig, SyntheticMarketData  # noqa: E402
from optlab.db.session import session_factory  # noqa: E402
from optlab.execution.costs import CostModel  # noqa: E402
from optlab.execution.fills import FillModel  # noqa: E402
from optlab.paper.engine import PaperEngine  # noqa: E402
from optlab.risk.manager import RiskLimits  # noqa: E402
from optlab.strategies.base import StrategyConfig  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy-from", required=True, help="experiment summary.json")
    ap.add_argument("--variant", required=True)
    ap.add_argument("--days", type=int, default=20)
    ap.add_argument("--synthetic-edge", type=float, default=0.0)
    ap.add_argument("--risk-pct", type=float, default=None)
    a = ap.parse_args()
    summ = json.load(open(a.strategy_from))
    v = summ["variants"][a.variant]
    from optlab.db.models import BacktestRun  # noqa
    cfg_g = load_config()
    sessions = session_factory(db_url(cfg_g))
    with sessions() as s:
        run = s.query(BacktestRun).filter_by(run_id=v["run_ids"]["realistic"]).one()
        cfg = StrategyConfig.from_dict(run.params)
    md = SyntheticMarketData(SyntheticConfig(start=date(2026, 1, 1), end=date(2026, 6, 30), seed=99,
                                             edge_strength=a.synthetic_edge))
    risk = {**cfg_g["risk"], **({"risk_per_trade_pct": a.risk_pct} if a.risk_pct else {})}
    eng = PaperEngine(md, [cfg], sessions, CostModel.from_config(cfg_g["costs"]),
                      FillModel.from_config(cfg_g["fills"]["realistic"]), RiskLimits.from_config(risk))
    days = md.trading_days()[: a.days]
    eng.run_replay(days[0], days[-1])
    print(eng.account())
    print(f"reports in {eng.report_dir}")
