"""Walk-forward validation: optimise on train window, trade the next unseen
window with the chosen parameters, roll forward, repeat. The concatenated
test-window trades are the honest out-of-sample record."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .splits import WFWindow, slice_trades
from .sweep import GridResult, select_robust


@dataclass
class WalkForwardResult:
    windows: pd.DataFrame        # one row per window: chosen params, IS/OOS stats
    oos_trades: pd.DataFrame


def walk_forward(gr: GridResult, windows: list[WFWindow], min_trades: int = 20) -> WalkForwardResult:
    rows, oos = [], []
    for w in windows:
        pt = select_robust(gr, w.train, min_trades=min_trades)
        res = gr.results[pt]
        tr = slice_trades(res.trades, w.train)
        te = slice_trades(res.trades, w.test)
        rows.append({"k": w.k, "train": f"{w.train.start}..{w.train.end}", "test": f"{w.test.start}..{w.test.end}",
                     "params": dict(zip(gr.grid, pt)),
                     "is_trades": len(tr), "is_exp_r": tr["r_multiple"].mean() if len(tr) else float("nan"),
                     "oos_trades": len(te), "oos_exp_r": te["r_multiple"].mean() if len(te) else float("nan"),
                     "oos_net_pnl": te["net_pnl"].sum() if len(te) else 0.0})
        if len(te):
            te = te.copy()
            te["wf_window"] = w.k
            oos.append(te)
    return WalkForwardResult(pd.DataFrame(rows), pd.concat(oos, ignore_index=True) if oos else pd.DataFrame())
