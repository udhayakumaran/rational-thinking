"""Strategy leaderboard: multi-dimensional, never ranked by total return.
Synthetic (VAL-*) and real (EXP-*) results are always listed separately."""
from __future__ import annotations

import pandas as pd

from .experiments import Registry


def leaderboard(reg: Registry, paper_consistency: dict | None = None) -> pd.DataFrame:
    rows = []
    for _, e in reg.experiments().iterrows():
        if e["status"] != "completed" or not e["summary"]:
            continue
        for vname, v in e["summary"]["variants"].items():
            oos, port, ver = v["walk_forward_oos"], v["portfolio"], v["verdict"]
            checks = {c["name"]: c for c in ver["checks"]}
            rows.append({
                "experiment": e["experiment_id"], "synthetic": e["is_synthetic"], "variant": vname,
                "verdict": ver["verdict"], "robustness_score": ver["score"],
                "oos_trades": oos.get("trades"), "oos_exp_r": oos.get("expectancy_r"),
                "oos_tstat": oos.get("expectancy_tstat"), "oos_pf": oos.get("profit_factor"),
                "plateau": (checks.get("parameter_plateau") or {}).get("value"),
                "regimes_positive": (checks.get("regime_consistency") or {}).get("value"),
                "pessimistic_exp_r": (checks.get("pessimistic_fill_expectancy") or {}).get("value"),
                "port_max_dd": port.get("max_drawdown_pct"), "port_trades": port.get("trades"),
                "fits_budget": v["expression"].get("share_budget_feasible_1pct"),
                "paper_consistency": (paper_consistency or {}).get(v.get("config_hash")),
                "fails": ", ".join(c["name"] for c in ver["checks"] if c["status"] == "FAIL"),
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(["synthetic", "robustness_score"], ascending=[True, False]).reset_index(drop=True)
