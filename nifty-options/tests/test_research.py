from datetime import date, timedelta

import numpy as np
import pandas as pd

from optlab.research.montecarlo import monte_carlo
from optlab.research.robustness import evaluate
from optlab.research.splits import chronological_split, walk_forward_windows
from optlab.research.sweep import neighbours

DAYS = [date(2024, 1, 1) + timedelta(days=i) for i in range(500)]


def test_chronological_split_is_ordered_and_disjoint():
    tr, va, te = chronological_split(DAYS)
    assert tr.end < va.start <= va.end < te.start and te.end == DAYS[-1]
    assert abs((tr.end - tr.start).days + 1 - 300) <= 1


def test_walk_forward_tests_never_overlap_and_follow_train():
    ws = walk_forward_windows(DAYS, 200, 50)
    assert len(ws) == 6
    for a, b in zip(ws, ws[1:]):
        assert a.test.end < b.test.start
    for w in ws:
        assert w.train.end < w.test.start


def test_neighbours():
    g = {"a": [1, 2, 3], "b": [10, 20]}
    assert sorted(neighbours((2, 10), g)) == [(1, 10), (2, 20), (3, 10)]


def test_monte_carlo_bounds():
    mc = monte_carlo([-1.0] * 50, n_trades=50, n_sims=200, risk_pct=0.01)
    assert mc.final_capital_pcts["p50"] == np.round(100_000 * 0.99 ** 50, 6) or abs(mc.median_final - 100_000 * 0.99 ** 50) < 1e-6
    assert mc.p_loss_10 == 1.0 and mc.expected_max_losing_streak == 50
    mc2 = monte_carlo([2.0, -1.0], n_sims=2000, n_trades=200)
    assert mc2.median_final > 100_000


def _trades(r, start=date(2023, 1, 2)):
    n = len(r)
    return pd.DataFrame({"r_multiple": r, "net_pnl": np.array(r) * 1000, "theoretical_pnl": np.array(r) * 1100,
                         "entry_ts": pd.date_range(start, periods=n, freq="3D"), "regime": "bull/normal"})


def test_gate_rejects_tiny_sample_and_negative_oos():
    v = evaluate(_trades([1.0] * 10), _trades([1.0] * 6), _trades([-0.5] * 4))
    assert v.verdict == "REJECT"
    names = {c.name: c.status for c in v.checks}
    assert names["sample_size_total"] == "FAIL" and names["oos_expectancy_r"] == "FAIL"


def test_gate_rejects_when_costs_destroy_edge():
    t = _trades([0.3, -0.31] * 200)
    t["theoretical_pnl"] = 50.0          # positive before costs
    t["net_pnl"] = -abs(t["net_pnl"]) * 0.01   # negative after costs
    v = evaluate(t, t.iloc[:200], t.iloc[200:])
    assert {c.name: c.status for c in v.checks}["edge_survives_costs"] == "FAIL"
