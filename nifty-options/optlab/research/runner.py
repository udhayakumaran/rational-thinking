"""End-to-end experiment pipeline:

  Hypothesis -> grid backtest (realistic fills) -> parameter choice on TRAIN
  (plateau-robust, not peak) -> VALIDATION -> TEST (touched once) ->
  walk-forward OOS -> fill-model stress (optimistic/pessimistic) ->
  Rs 1L portfolio simulation with real risk limits -> Monte Carlo ->
  anti-overfitting gate -> verdict + report.

Every variant in an experiment receives the IDENTICAL signal stream (same
signal params), so differences come from the option expression only.
"""
from __future__ import annotations

import math
import multiprocessing as mp
import time
from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from ..backtest.engine import Backtester, BacktestResult, CoreConfig
from ..backtest.metrics import by_group, full_metrics, trade_metrics
from ..config import ROOT, db_url, load_config, load_yaml
from ..data.interfaces import MarketData
from ..db.session import session_factory
from ..execution.costs import CostModel
from ..execution.fills import FillModel
from ..risk.manager import RiskLimits
from ..strategies.base import Strategy, StrategyConfig
from ..strategies.regime import build_day_contexts
from .experiments import Registry, jsonable, write_json
from .montecarlo import monte_carlo
from .robustness import Thresholds, evaluate
from .splits import chronological_split, slice_trades, walk_forward_windows
from .sweep import GridResult, neighbours, plateau_scores, run_grid, select_robust, set_path
from .walkforward import walk_forward

_G: dict = {}  # fork-inherited state for parallel grid runs


def _run_point(cfg: StrategyConfig) -> BacktestResult:
    bt: Backtester = _G["bt"]
    return bt.run(Strategy(cfg, bt.md))


def make_market_data(spec: dict) -> MarketData:
    src = spec.get("source", "synthetic")
    if src == "synthetic":
        from ..data.synthetic import SyntheticConfig, SyntheticMarketData
        p = dict(spec.get("synthetic", {}))
        for k in ("start", "end"):
            if k in p:
                p[k] = date.fromisoformat(str(p[k]))
        return SyntheticMarketData(SyntheticConfig(**p))
    if src == "db":
        from ..data.store import StoredMarketData
        cfg = load_config()
        return StoredMarketData(db_url(cfg), spec["data_version"], underlying=spec.get("underlying", "NIFTY"),
                                bar_minutes=spec.get("bar_minutes", 5))
    raise ValueError(f"unknown data source {src}")


def _grid_parallel(bt: Backtester, base: StrategyConfig, grid: dict, workers: int, log) -> GridResult:
    import itertools
    keys = list(grid)
    points = list(itertools.product(*(grid[k] for k in keys)))
    cfgs = []
    for pt in points:
        c = base
        for k, v in zip(keys, pt):
            c = set_path(c, k, v)
        cfgs.append(c)
    if workers <= 1 or len(cfgs) == 1:
        res = [_run_point_bt(bt, c) for c in cfgs]
    else:
        _G["bt"] = bt
        with mp.get_context("fork").Pool(workers) as pool:
            res = pool.map(_run_point, cfgs)
    log(f"    grid: {len(points)} points done")
    return GridResult(grid, points, dict(zip(points, res)))


def _run_point_bt(bt, cfg):
    return bt.run(Strategy(cfg, bt.md))


def run_experiment(spec_path: str | Path, workers: int = 4, db: str | None = None, log=print) -> dict:
    spec = load_yaml(spec_path)
    gcfg = load_config()
    exp_id = spec["id"]
    t0 = time.time()
    md = make_market_data(spec["data"])
    log(f"[{exp_id}] data={md.data_version} synthetic={md.is_synthetic} days={len(md.trading_days())}")
    prefix = "VAL" if md.is_synthetic else "EXP"
    if not exp_id.startswith(prefix):
        raise ValueError(f"{'synthetic' if md.is_synthetic else 'real'}-data experiments must use a {prefix}-### id")

    sessions = session_factory(db or db_url(gcfg))
    reg = Registry(sessions)
    reg.register(exp_id, spec["title"], spec["hypothesis"], spec, md.data_version, md.is_synthetic)

    costs = CostModel.from_config(gcfg["costs"])
    limits = RiskLimits.from_config({**gcfg["risk"], **spec.get("risk", {})})
    fills = {k: FillModel.from_config(v) for k, v in gcfg["fills"].items()}
    contexts = build_day_contexts(md)
    core = CoreConfig(mode="research", fill_delay_bars=gcfg["engine"]["fill_delay_bars"])
    bt = {k: Backtester(md, fm, costs, limits, core, contexts) for k, fm in fills.items()}

    days = md.trading_days()
    split = chronological_split(days, tuple(spec.get("split", (0.6, 0.2, 0.2))))
    train, valid, test = split
    wf_cfg = spec.get("walk_forward", {})
    wfw = walk_forward_windows(days, wf_cfg.get("train_days", 250), wf_cfg.get("test_days", 63),
                               anchored=wf_cfg.get("anchored", False))
    th = Thresholds(**spec.get("thresholds", {}))
    grid = spec.get("grid", {})
    base = StrategyConfig.from_dict(spec["base_strategy"])
    out_dir = ROOT / "reports" / exp_id
    out_dir.mkdir(parents=True, exist_ok=True)

    variants_out = {}
    for vname, overrides in spec["variants"].items():
        log(f"  variant {vname}")
        overrides = dict(overrides or {})
        v_limits = RiskLimits.from_config({**gcfg["risk"], **spec.get("risk", {}), **overrides.pop("risk", {})})
        v_port = Backtester(md, fills["realistic"], costs, v_limits,
                            CoreConfig(mode="portfolio", fill_delay_bars=core.fill_delay_bars), contexts)
        vcfg = base
        for path, val in _flatten(overrides).items():
            vcfg = set_path(vcfg, path, val)
        vcfg = replace(vcfg, name=f"{base.name}:{vname}")
        gr = _grid_parallel(bt["realistic"], vcfg, grid, workers, log) if grid else \
            GridResult({"_": [0]}, [(0,)], {(0,): bt["realistic"].run(Strategy(vcfg, md))})
        chosen_pt = select_robust(gr, train, min_trades=th.reject_below_trades) if grid else (0,)
        chosen_cfg = vcfg
        if grid:
            for k, v in zip(gr.grid, chosen_pt):
                chosen_cfg = set_path(chosen_cfg, k, v)
        res = gr.results[chosen_pt]
        tr_t, va_t, te_t = (slice_trades(res.trades, w) for w in split)
        wf = walk_forward(gr, wfw, min_trades=max(10, th.reject_below_trades // 2)) if grid else None
        oos = wf.oos_trades if (wf is not None and len(wf.oos_trades)) else te_t
        # plateau evaluated on validation+test (data not used to choose parameters)
        plateau_same = None
        if grid and len(gr.points) > 1:
            from .splits import Window
            oos_win = Window("val+test", valid.start, test.end)
            ps = plateau_scores(gr, oos_win)
            row = ps[np.all([ps[k] == v for k, v in zip(gr.grid, chosen_pt)], axis=0)]
            plateau_same = float(row["nb_same_sign"].iloc[0]) if len(row) and np.isfinite(row["nb_same_sign"].iloc[0]) else 0.0
        # fill-model stress on the chosen config
        stress = {}
        for fm_name in ("optimistic", "pessimistic"):
            r = bt[fm_name].run(Strategy(chosen_cfg, md))
            stress[fm_name] = r
        pess_oos = slice_trades(stress["pessimistic"].trades, test)
        # Rs 1L portfolio simulation with full risk limits
        port = v_port.run(Strategy(chosen_cfg, md))
        port_m = full_metrics(port)
        mc = monte_carlo(oos["r_multiple"], v_limits.initial_capital, v_limits.risk_per_trade_pct,
                         n_trades=max(len(oos), 100), n_sims=spec.get("monte_carlo", {}).get("n_sims", 5000),
                         block=spec.get("monte_carlo", {}).get("block", 5)) if len(oos) else None
        verdict = evaluate(res.trades, tr_t, oos, pessimistic_oos_trades=pess_oos, plateau_same_sign=plateau_same,
                           portfolio_max_dd=port_m.get("max_drawdown_pct") if port_m.get("trades", 0) else None, mc_p_dd20=mc.p_dd_20 if mc else None, th=th)
        # persist chosen-config runs
        run_ids = {}
        for tag, r in (("realistic", res), ("optimistic", stress["optimistic"]),
                       ("pessimistic", stress["pessimistic"]), ("portfolio", port)):
            run_ids[tag] = reg.save_run(r, full_metrics(r), exp_id, f"{vname}:{tag}", chosen_cfg,
                                        store_trades=tag in ("realistic", "portfolio"))
        v_out = {
            "label": Strategy(chosen_cfg, md).label, "chosen_params": dict(zip(gr.grid, chosen_pt)) if grid else {},
            "config_hash": chosen_cfg.config_hash, "run_ids": run_ids,
            "full": full_metrics(res), "train": trade_metrics(tr_t), "validation": trade_metrics(va_t),
            "test": trade_metrics(te_t), "walk_forward_oos": trade_metrics(oos),
            "walk_forward_windows": wf.windows.to_dict("records") if wf is not None else [],
            "fills": {k: trade_metrics(slice_trades(v.trades, test)) for k, v in
                      (("optimistic", stress["optimistic"]), ("realistic", res), ("pessimistic", stress["pessimistic"]))},
            "portfolio": port_m,
            "portfolio_rejections": port.rejections["stage"].value_counts().to_dict() if len(port.rejections) else {},
            "portfolio_rejection_reasons": _top_reasons(port.rejections),
            "monte_carlo": mc.to_dict() if mc else None,
            "by_regime": by_group(res.trades, "regime").reset_index().to_dict("records"),
            "by_vol_regime": by_group(res.trades, "vol_regime").reset_index().to_dict("records"),
            "by_direction": by_group(res.trades, "direction").reset_index().to_dict("records"),
            "by_exit_reason": by_group(res.trades, "exit_reason").reset_index().to_dict("records"),
            "by_year": by_group(res.trades.assign(year=pd.to_datetime(res.trades["entry_ts"]).dt.year), "year")
                .reset_index().to_dict("records") if len(res.trades) else [],
            "expression": _expression_stats(res.trades),
            "sensitivity_train": gr.table(train).to_dict("records") if grid else [],
            "sensitivity_valtest": gr.table(chosen_window(valid, test)).to_dict("records") if grid else [],
            "verdict": verdict.to_dict(),
        }
        variants_out[vname] = v_out
        res.trades.to_csv(out_dir / f"trades_{vname}.csv", index=False)
        if len(port.rejections):
            port.rejections.to_csv(out_dir / f"portfolio_rejections_{vname}.csv", index=False)
        log(f"    -> {verdict.verdict} score={verdict.score} OOS E[R]={v_out['walk_forward_oos'].get('expectancy_r')}")

    summary = {"experiment_id": exp_id, "data_version": md.data_version, "is_synthetic": md.is_synthetic,
               "split": [jsonable(w.__dict__) for w in split], "n_wf_windows": len(wfw),
               "variants": variants_out, "elapsed_s": round(time.time() - t0, 1)}
    overall = _overall_verdict(variants_out)
    reg.complete(exp_id, overall, summary)
    write_json(out_dir / "summary.json", summary)
    from .report import experiment_markdown
    (out_dir / "report.md").write_text(experiment_markdown(spec, summary))
    log(f"[{exp_id}] done in {summary['elapsed_s']}s -> {out_dir/'report.md'}")
    return summary


def chosen_window(valid, test):
    from .splits import Window
    return Window("val+test", valid.start, test.end)


def _flatten(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in (d or {}).items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        else:
            out[key] = v
    return out


def _top_reasons(rej: pd.DataFrame, n: int = 5) -> dict:
    if rej.empty:
        return {}
    r = rej["reasons"].explode().astype(str).str.replace(r"\d+", "#", regex=True)
    return r.value_counts().head(n).to_dict()


def _expression_stats(t: pd.DataFrame) -> dict:
    if t.empty:
        return {}
    return {"avg_risk_per_lot": float(t["risk_per_lot"].mean()),
            "avg_max_reward_per_lot": float(t["max_reward_per_lot"].replace([np.inf], np.nan).mean()),
            "avg_entry_theta_rupees_per_day": float((t["net_theta"] * t["lot_size"]).mean()),
            "avg_entry_vega_rupees": float((t["net_vega"] * t["lot_size"]).mean()),
            "avg_entry_delta": float(t["net_delta"].mean()),
            "avg_fees_per_trade": float(t["fees"].mean()),
            "avg_slippage_per_trade": float(t["slippage_rupees"].mean()),
            "slippage_plus_fees_in_r": float(((t["fees"] + t["slippage_rupees"]) / t["account_risk"]).mean()),
            "theoretical_exp_r": float((t["theoretical_pnl"] / t["account_risk"]).mean()),
            "pnl_per_rupee_risked": float(t["net_pnl"].sum() / t["account_risk"].sum()),
            "share_budget_feasible_1pct": float(t["budget_feasible_at_1pct"].mean())}


def _overall_verdict(v: dict) -> str:
    vs = [x["verdict"]["verdict"] for x in v.values()]
    if "PROMOTE_TO_PAPER" in vs:
        return "SOME_VARIANTS_PROMOTABLE"
    if "FLAGGED" in vs:
        return "FLAGGED"
    return "REJECT_ALL"
