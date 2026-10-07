#!/usr/bin/env python3
"""Import real data, run data-quality checks, and store it under a content-hash data_version.

Generic intraday CSVs:
    python scripts/import_data.py intraday --index nifty_5m.csv --futures nifty_fut_5m.csv \
        --vix vix_5m.csv --options nifty_opts_5m.csv --bar-minutes 5 --label start [--colmap map.yaml]
NSE F&O bhavcopies (EOD; no bid/ask -> estimated spreads):
    python scripts/import_data.py bhavcopy --files fo*.csv --index nifty_daily.csv

Research is blocked (exit code 2) if any ERROR-level quality issue is found, unless --force.
"""
import argparse
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from optlab.config import db_url, load_config  # noqa: E402
from optlab.core.calendar import TradingCalendar, lot_size_on  # noqa: E402
from optlab.data import loaders as L  # noqa: E402
from optlab.data.quality import check_options, check_underlying, summarize  # noqa: E402
from optlab.data.store import write_normalized  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["intraday", "bhavcopy"])
    ap.add_argument("--index"); ap.add_argument("--futures"); ap.add_argument("--vix"); ap.add_argument("--options")
    ap.add_argument("--files", nargs="*")
    ap.add_argument("--bar-minutes", type=int, default=5)
    ap.add_argument("--label", choices=["start", "end"], default="start", help="vendor bar timestamp convention")
    ap.add_argument("--colmap")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    colmap = yaml.safe_load(open(a.colmap)) if a.colmap else None
    cal = TradingCalendar()
    if a.kind == "intraday":
        paths = [p for p in (a.index, a.futures, a.vix, a.options) if p]
        idx = L.load_candles_csv(a.index, a.bar_minutes, a.label, colmap)
        fut = L.load_candles_csv(a.futures, a.bar_minutes, a.label, colmap) if a.futures else None
        vix = L.load_candles_csv(a.vix, a.bar_minutes, a.label, colmap) if a.vix else None
        opt = L.load_options_csv(a.options, a.bar_minutes, a.label, colmap)
        interval = a.bar_minutes
    else:
        files = sorted(f for pat in a.files for f in glob.glob(pat))
        paths = files + ([a.index] if a.index else [])
        parts, lots = zip(*(L.load_nse_bhavcopy(f) for f in files))
        opt = pd.concat(parts, ignore_index=True)
        idx = L.load_candles_csv(a.index, 375, "end", colmap) if a.index else pd.DataFrame()
        fut = vix = None
        interval = 375
    version = L.content_version(paths)
    issues = check_underlying(idx, interval) + check_options(
        opt, idx.set_index("ts")["close"] if len(idx) else None, calendar=cal)
    ok, rep = summarize(issues)
    print(rep.to_string())
    out = Path(__file__).resolve().parents[1] / "reports" / "data_quality"
    out.mkdir(parents=True, exist_ok=True)
    rep.to_csv(out / f"{version}.csv", index=False)
    if not ok and not a.force:
        print(f"\nERROR-level data issues; not importing {version}. Fix the data or pass --force (documented).")
        sys.exit(2)
    ex = L.expiries_from_options(opt, lot_size_on, cal)
    n = write_normalized(db_url(load_config()), version, "NIFTY", {"INDEX": idx, "FUT": fut, "VIX": vix},
                         opt.drop(columns=[c for c in ("settle",) if c in opt]), ex, interval)
    print(f"\nimported data_version={version}: {n}\nSet this data_version in config/experiments/EXP-*.yaml")


if __name__ == "__main__":
    main()
