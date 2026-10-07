#!/usr/bin/env python3
"""Run a registered experiment spec end to end.

    python scripts/run_experiment.py config/experiments/VAL-001.yaml --workers 4
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from optlab.research.runner import run_experiment  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--db", default=None, help="override database URL")
    a = ap.parse_args()
    run_experiment(a.spec, workers=a.workers, db=a.db)
