# NIFTY Options Lab - systematic research & PAPER-trading platform

Purpose: decide, with evidence, whether a defined-risk NIFTY options strategy has **robust positive expectancy after
realistic costs and risk constraints**, and then check that paper trading behaves like the backtest. Finding nothing
is an acceptable answer.

**Paper only.** No order-routing code exists; a test enforces it. Starting paper capital Rs 1,00,000; 1% risk/trade.

## Status
| Phase | State |
|---|---|
| 1 Architecture, data-source assessment, experiment design | done - `docs/PHASE1_ASSESSMENT.md` |
| 2 Data | **blocked on a data-source decision** (cost + credentials). Importers + quality checks are ready; this environment's network blocks NSE/broker hosts |
| 3 Backtester (costs, slippage, fills, tests) | done; validated with null + positive-control synthetic markets |
| 4-5 Baseline long options, debit spreads | implemented; EXP-001 spec ready to run on real data |
| 6 Research framework (grids, plateau, walk-forward, Monte Carlo, gate, registry, leaderboard) | done |
| 7 Risk engine (Rs 1L, sizing by max loss, limits) | done |
| 8 Paper trading | engine + persistence + daily report done; replay mode works; live data adapter awaits vendor choice |
| 9 Dashboard | Streamlit app done |
| 10 Evaluation | backtest-vs-paper comparison implemented; needs real paper trades |

## Layout
```
nifty-options/
  optlab/            the package
    core/            contracts, payoffs & exact risk profiles, pricing, calendar
    data/            MarketData interface, synthetic controls, DB store, loaders, quality checks
    db/              SQLAlchemy schema (SQLite -> PostgreSQL by URL)
    strategies/      signals, regime, structure builders, exits, Strategy interface
    execution/       fill models, Indian transaction costs
    risk/            sizing + portfolio limits
    backtest/        TradingCore + Backtester, metrics
    research/        splits, sweeps, walk-forward, Monte Carlo, gate, registry, leaderboard, runner, reports
    paper/           paper engine, live-data plumbing (read-only), daily report, backtest-vs-paper
    dashboard/       Streamlit UI
  config/            default.yaml (costs, risk, fills, DB) + experiments/*.yaml
  docs/              ARCHITECTURE, STRATEGY_RESEARCH, RISK_MANAGEMENT, PAPER_TRADING, EXPERIMENTS, PHASE1_ASSESSMENT
  scripts/           run_experiment, import_data, paper_replay, leaderboard
  reports/           experiment reports (VAL-*/EXP-*), data-quality reports, paper daily reports
  tests/             pytest suite
```

## Quick start
```bash
cd nifty-options
pip install -e .[dev]
python -m pytest -q                                              # full suite
python scripts/run_experiment.py config/experiments/VAL-001.yaml # pipeline validation on synthetic null market
python scripts/leaderboard.py
streamlit run optlab/dashboard/app.py
```
Real data (after choosing a vendor):
```bash
python scripts/import_data.py intraday --index idx.csv --futures fut.csv --vix vix.csv --options opts.csv --bar-minutes 5
# put the printed data_version into config/experiments/EXP-001.yaml, then
python scripts/run_experiment.py config/experiments/EXP-001.yaml
```

## Reading results
* `VAL-*` = synthetic pipeline validation. Says nothing about the market.
* `EXP-*` = real-data research. Immutable once run; changes need a new ID.
* Verdicts: `REJECT` (discard - don't rescue), `FLAGGED`, `PROMOTE_TO_PAPER`.
