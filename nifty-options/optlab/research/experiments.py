"""Append-only experiment registry and run persistence.

* Every experiment has an ID (EXP-### for real-data research, VAL-### for
  pipeline-validation runs on synthetic data).
* An ID can be registered once. Completed experiments are never modified;
  re-running means registering a new ID (e.g. EXP-001-R2) that references it.
* Each stored run records code version (git commit + dirty flag), strategy
  config hash/version, parameters, data version and timestamp.
"""
from __future__ import annotations

import json
import math
import subprocess
import uuid
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..backtest.engine import BacktestResult
from ..db.models import BacktestRun, BacktestTradeRow, ExperimentRow, RejectedSignalRow, StrategyConfigRow
from ..strategies.base import StrategyConfig


class ExperimentExists(Exception):
    pass


def code_version(repo_dir: str | Path | None = None) -> str:
    try:
        cwd = str(repo_dir or Path(__file__).resolve().parents[2])
        sha = subprocess.check_output(["git", "rev-parse", "--short=12", "HEAD"], cwd=cwd, text=True).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain", "--", "."], cwd=cwd, text=True).strip()
        return sha + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, (datetime, date, pd.Timestamp)):
        return o.isoformat()
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return None if math.isnan(f) else (str(f) if math.isinf(f) else f)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return [jsonable(v) for v in o.tolist()]
    return o


class Registry:
    def __init__(self, sessions: sessionmaker[Session]):
        self.sessions = sessions

    def register(self, experiment_id: str, title: str, hypothesis: str, spec: dict, data_version: str,
                 is_synthetic: bool) -> None:
        with self.sessions() as s:
            if s.scalar(select(ExperimentRow).where(ExperimentRow.experiment_id == experiment_id)):
                raise ExperimentExists(f"{experiment_id} already registered; experiments are immutable - use a new ID")
            s.add(ExperimentRow(experiment_id=experiment_id, title=title, hypothesis=hypothesis, spec=jsonable(spec),
                                status="registered", code_version=code_version(), data_version=data_version,
                                is_synthetic=is_synthetic))
            s.commit()

    def complete(self, experiment_id: str, verdict: str, summary: dict) -> None:
        with self.sessions() as s:
            row = s.scalar(select(ExperimentRow).where(ExperimentRow.experiment_id == experiment_id))
            if row is None:
                raise KeyError(experiment_id)
            if row.status != "registered":
                raise ExperimentExists(f"{experiment_id} already completed; results are immutable")
            row.status, row.verdict, row.summary = "completed", verdict, jsonable(summary)
            s.commit()

    def save_strategy_config(self, cfg: StrategyConfig) -> None:
        with self.sessions() as s:
            if not s.scalar(select(StrategyConfigRow).where(StrategyConfigRow.config_hash == cfg.config_hash)):
                s.add(StrategyConfigRow(name=cfg.name, version=cfg.version, config_hash=cfg.config_hash,
                                        params=jsonable(cfg.to_dict())))
                s.commit()

    def save_run(self, result: BacktestResult, metrics: dict, experiment_id: str | None, variant: str,
                 cfg: StrategyConfig, store_trades: bool = True) -> str:
        run_id = f"{experiment_id or 'adhoc'}-{uuid.uuid4().hex[:10]}"
        self.save_strategy_config(cfg)
        m = result.meta
        with self.sessions() as s:
            s.add(BacktestRun(run_id=run_id, experiment_id=experiment_id, variant=variant, strategy_name=cfg.name,
                              strategy_version=cfg.version, params=jsonable(cfg.to_dict()), code_version=code_version(),
                              data_version=m["data_version"], is_synthetic=m["is_synthetic"], fill_model=m["fill_model"],
                              period_start=date.fromisoformat(m["start"]) if m.get("start") else None,
                              period_end=date.fromisoformat(m["end"]) if m.get("end") else None,
                              metrics=jsonable({**metrics, "mode": m.get("mode")})))
            if store_trades:
                for rec in result.trades.to_dict("records"):
                    s.add(BacktestTradeRow(run_id=run_id, record=jsonable(rec)))
                for rj in result.rejections.to_dict("records"):
                    s.add(RejectedSignalRow(ts=pd.Timestamp(rj["ts"]).to_pydatetime(), mode="backtest", run_id=run_id,
                                            strategy=str(rj.get("strategy")), direction=str(rj.get("direction")),
                                            stage=str(rj.get("stage")), reasons=jsonable(rj.get("reasons")),
                                            details=jsonable(rj.get("details") or {})))
            s.commit()
        return run_id

    def experiments(self) -> pd.DataFrame:
        with self.sessions() as s:
            rows = s.scalars(select(ExperimentRow)).all()
            return pd.DataFrame([{"experiment_id": r.experiment_id, "title": r.title, "status": r.status,
                                  "verdict": r.verdict, "is_synthetic": r.is_synthetic, "data_version": r.data_version,
                                  "code_version": r.code_version, "created_at": r.created_at, "summary": r.summary}
                                 for r in rows])


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(obj), indent=2, sort_keys=True))
