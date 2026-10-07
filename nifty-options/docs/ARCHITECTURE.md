# Architecture

## Principles
* Simplest robust design: one process, one Python package, one relational DB. No distributed infrastructure.
* Separation of concerns: **signal** (when/direction) / **structure** (which legs) / **risk** (whether and how many) /
  **execution simulation** (at what price and cost). Each is swappable and unit-tested independently.
* **One trading core** for backtest and paper. Verified by `tests/test_paper.py` (trade-for-trade parity).
* **No look-ahead by construction**: bar timestamps are bar *ends*; signals use bars <= t; fills happen at t + 1 bar at
  that bar's quotes; regime/day context uses only prior days plus the opening print. Causality is tested by truncation
  (`test_indicators_and_signals_are_causal`).
* **Paper only.** No order-routing code exists; a test scans for it.

## Package map (`optlab/`)

| Module | Responsibility |
|---|---|
| `core/instruments.py` | contracts, legs, structures; exact expiry payoff, max loss/gain, breakevens (piecewise-linear analysis) |
| `core/pricing.py` | Black-Scholes price/greeks/IV (for IV & greeks from *observed* prices, and synthetic data) |
| `core/calendar.py` | session times, NIFTY expiry rules (Thu -> Tue from 2025-09-01), holidays, lot-size schedule |
| `core/market.py` | `Quote`, `UnderlyingState` value types |
| `data/interfaces.py` | **`MarketData`** - the only data interface strategies and engines see |
| `data/synthetic.py` | labelled synthetic generator: null and positive-control markets |
| `data/store.py` | DB-backed `MarketData` for real data; bulk writer |
| `data/loaders.py` | vendor CSV + NSE bhavcopy importers; content-hash `data_version` |
| `data/quality.py` | data-quality checks (timestamps, OHLC, strikes, expiries, crossed/one-sided/wide quotes, stale, below-intrinsic) |
| `strategies/signals.py` | signal generators (ORB15 with individually switchable filters) |
| `strategies/regime.py` | ex-ante regime + day context (trend, vol percentile, vol dynamics, gap, expiry day) |
| `strategies/structures.py` | expression builders: long option, debit spread, straddle, strangle, butterfly, iron condor |
| `strategies/exits.py` | stop, % max profit, R target, trailing, time stop, invalidation, EOD, pre-expiry, max hold |
| `strategies/base.py` | `Strategy` interface: generate_signal, build_position, calculate_max_risk, calculate_expected_reward, check_liquidity, check_risk_limits, update (enter/exit are executed by the core) |
| `execution/fills.py` | optimistic / realistic / pessimistic per-leg fills; tick rounding against the trader; estimated spreads |
| `execution/costs.py` | brokerage, exchange, SEBI, stamp, STT (dated schedule), GST, exercise STT |
| `risk/manager.py` | sizing by max theoretical loss + costs; per-trade budget; open-risk, daily, weekly limits; halts |
| `backtest/engine.py` | `TradingCore` (all trading logic) + `Backtester` |
| `backtest/metrics.py` | expectancy (Rs and R), PF, payoff, streaks, drawdowns, CAGR, Sharpe, Sortino, Calmar, holding times |
| `research/*` | splits, grid & plateau, walk-forward, Monte Carlo, gate, registry, leaderboard, runner, reports |
| `paper/*` | `PaperEngine`, read-only live data plumbing, daily report, backtest-vs-paper comparison |
| `dashboard/app.py` | Streamlit monitoring UI (read-only) |
| `db/models.py` | all persistent tables |

## Data flow for one bar

```
ts (bar end) -> bars<=ts -> Signal.compute_day -> events at ts
TradingCore.step(ts):
  1. fill pending exits (decided at ts-1) at quotes(ts)
  2. fill pending entries: build structure at ts, price legs with FillModel, liquidity checks,
     max loss from exact risk profile on fill prices + est. round-trip costs, RiskManager sizing -> open | reject(logged)
  3. mark open positions at mid, evaluate exit rules -> pending exit for ts+1
  4. queue new signals for ts+1
```

## Persistence
Tables: market_ticks, underlying_candles, option_quotes, option_chain_snapshots, expiries, signals, rejected_signals,
strategy_configs, experiments, backtest_runs, backtest_trades, paper_orders, paper_fills, paper_positions,
paper_trades, daily_metrics, account_equity. Moving to PostgreSQL = set `database.url` in `config/default.yaml`
(`postgresql+psycopg://...`) and `pip install .[postgres]`.

## Adding another underlying
`MarketData.underlying`, strike step (`StructureSpec.strike_step`), lot-size source and the calendar's expiry rule are
the only NIFTY-specific parameters. BANKNIFTY/SENSEX need a calendar rule set and a loader; nothing else changes.
