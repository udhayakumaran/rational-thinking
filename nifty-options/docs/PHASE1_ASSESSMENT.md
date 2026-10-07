# Phase 1 deliverable - architecture, data, costs, methodology, first experiments, risks

Status date: 2026-10-07. Everything here is a starting position, to be revised against evidence.

## 1. Proposed architecture (summary - details in ARCHITECTURE.md)

One Python package (`optlab`) with strictly separated layers:

```
MarketData (interface)  ->  Signal  ->  StructureBuilder  ->  Liquidity  ->  RiskManager  ->  FillModel + CostModel
   synthetic | DB (real) | live          (when/which way)     (which legs)     (tradable?)     (how many lots?)   (what price/fees?)
                                   \______________________ TradingCore.step() ______________________/
                                          driven by Backtester (history)  or  PaperEngine (live/replay)
```

The single most important design decision: **backtest and paper trading run the same `TradingCore` code**. A test
(`tests/test_paper.py`) proves a bar-by-bar paper replay reproduces the backtest trade-for-trade. Any later gap between
backtest and paper therefore comes from the market (fills, data, regime), not from code drift.

Storage: SQLAlchemy models (SQLite now, PostgreSQL by changing one URL). Research tables are append-only;
every run stores code version (git SHA + dirty flag), strategy config hash/version, parameters, data version (content
hash) and timestamp.

## 2. Directory structure

See README.md. The spec's `/strategies /backtest /execution /risk /paper /dashboard /research /data` folders are
sub-packages of `optlab/`; `config/ docs/ reports/ tests/ scripts/ data/` sit at the project root. The project lives in
`nifty-options/` because this repository already contains an unrelated Remotion video project.

## 3. Recommended market-data source

| Need | Recommendation | Why | Cost (approx., verify) |
|---|---|---|---|
| Historical intraday NIFTY options **with OI, 1-min, expired contracts** | **Dhan Data API** (expired-options endpoint, ~5y, ATM +/- strikes) *or* **TrueData / Global Datafeeds (GDFL)** historical vendor files | Expired-contract intraday history is the hard part; most broker APIs (e.g. Kite) do not serve expired option contracts | Dhan data API add-on is a low monthly fee; vendor history is a one-off purchase in the tens of thousands of rupees range |
| Historical **bid/ask** | Only tick/quote vendors (GDFL/TrueData tick, NSE paid tick data) | 1-min OHLC has no spreads. Without them fills are *estimated* and the gate flags it | Higher; decide after OHLC research shows anything worth confirming |
| Free EOD sanity data | NSE F&O bhavcopy (legacy + UDiFF) | Free, authoritative settle/close/OI/lot size; supports daily-horizon studies only | Free |
| Live paper data | Broker market-data websocket (Dhan / Zerodha Kite Connect / Upstox) | Real-time chain with **bid/ask depth**, needed for honest paper fills | Kite Connect ~Rs 500/month data; Dhan/Upstox data APIs low/no cost with an account |

Recommendation: **one broker market-data subscription that also serves expired intraday options (Dhan is the current
best fit if its expired-options API meets the quality checks), plus free NSE bhavcopies as an independent cross-check.**
Market-data-only API keys; no order permissions requested.

**This is a decision for you (monetary cost + credentials).** Nothing is purchased or connected yet.

## 4. Historical-data availability assessment

* This build environment's network policy blocks NSE, Yahoo and broker hosts, so **no real data has been loaded**. All
  numbers produced so far come from labelled synthetic data and validate the *engine*, not any strategy.
* Realistic expectations once data is purchased:
  * Weekly NIFTY options exist since 2019; 1-min OHLC+OI for expired contracts ~2019/2021 onwards depending on vendor;
    that's roughly 1,200-1,700 sessions - enough for intraday signals that fire ~1x/day (hundreds of trades), thin for
    rarer setups.
  * Regime changes inside the sample that must be modelled, not averaged away: lot size changes (75 -> 50 -> 25 -> 75 ->
    65, dates to verify), the Nov-2024 SEBI F&O changes (contract size, one weekly expiry per exchange, upfront premium),
    the Sep-2025 move of NIFTY expiry from Thursday to Tuesday, STT increases (Oct-2024, and the 2026 Budget revision -
    verify). Results are reported **by year** so a single structural period cannot carry a strategy.
  * Bid/ask history will most likely be absent; the platform then uses an estimated spread and flags every trade
    (`spread_estimated`), and the gate requires pessimistic-fill survival.

## 5. Live-data approach

`optlab/paper/live.py` defines a **read-only** `MarketDataSource` (index bars, futures bars, VIX, option chain with
bid/ask, instrument master). A vendor adapter fills `LiveMarketData` every 5-minute bar; the `PaperEngine` then calls
`on_bar(ts)`. The project contains no order-routing code, and `tests/test_no_live_trading.py` fails the build if any
appears. Until credentials exist, the paper engine runs in **replay mode** against stored data (`scripts/paper_replay.py`).

## 6. Cost and slippage assumptions (all configurable, `config/default.yaml`)

| Item | Default | Notes |
|---|---|---|
| Brokerage | Rs 20 per executed order (per leg, per side) | A 2-leg spread round trip = 4 orders = Rs 80 + GST |
| NSE transaction charge | 0.03503% of premium from Oct-2024; ~0.0495% before (VERIFY older history) | Dated schedule |
| SEBI fee | Rs 10/crore | |
| Stamp duty | 0.003% of premium, buy side | |
| STT | 0.017% (pre-Jun-2016), 0.05%, 0.0625% (Apr-2023), 0.1% (Oct-2024), 0.15% (Apr-2026) of sell premium; exercise 0.125% -> 0.15% of intrinsic | Dated schedule; applied by trade date |
| GST | 18% on brokerage + exchange + SEBI | |
| Fill - optimistic | mid | Never used for decisions |
| Fill - realistic (default) | mid +/- half the half-spread + 1 tick, per leg | |
| Fill - pessimistic | touch (ask for buys, bid for sells) + 1 tick, per leg | Gate requires positive expectancy here |
| Unobserved spreads | half-spread = max(0.05, 0.5% x price); 0.10 below Rs 5 | flagged `spread_estimated` |
| Latency | decisions at bar t fill at bar t+1's quotes | no same-bar fills |

Scale of the problem for small debit spreads: round-trip fees on a 2-leg, 1-lot spread are ~Rs 100-130 before
slippage. Against a Rs 1,000 risk unit that is **10-13% of R per trade before any edge** - see the risk section below.

## 7. Experiment methodology

Hypothesis -> backtest -> validate -> stress -> paper -> compare -> accept/reject, implemented in
`optlab/research/runner.py` (details in STRATEGY_RESEARCH.md):

1. Grid backtest (1 lot, realistic fills, all costs) over the full period.
2. Choose parameters on TRAIN (first 60%) by **neighbourhood-robust value** (min of point and neighbour mean), never the
   raw peak.
3. Report VALIDATION (next 20%) and TEST (last 20%).
4. Rolling walk-forward (250-day train / 63-day test): the concatenated test windows are the OOS record used by the gate.
5. Stress: same config under optimistic / pessimistic fills.
6. Rs 1L portfolio simulation with every risk limit enforced (discrete lots; oversized trades rejected and logged).
7. Monte Carlo block bootstrap of OOS R-multiples (5,000 paths).
8. Anti-overfitting gate -> REJECT / FLAGGED / PROMOTE_TO_PAPER, robustness score, markdown report.

Pipeline integrity is itself tested with controls: a **null** synthetic market (must find nothing) and a **positive
control** with a planted ORB continuation (must find it). See EXPERIMENTS.md, VAL-001/VAL-002.

## 8. First five experiments (specs in `config/experiments/`)

| ID | Question | Variants |
|---|---|---|
| EXP-001 | Same ORB15 signal: which expression is best? | A ATM long option; B ATM->+100 spread; C ITM50->OTM100 spread; D ATM->+300 spread; grid momentum x stop |
| EXP-002 | Does each filter add OOS value? (one at a time) | baseline; no-VWAP; VIX max; VIX min; trend-align; gap cap; skip expiry day; OR width; RSI |
| EXP-003 | Which exit? | SL50/EOD; TP 25/40/50/70% of max profit; no stop; OR-mid invalidation; time stop; trailing; hold to expiry |
| EXP-004 | Is Rs 1L sufficient? | 0.5/1/1.5/2% risk x 50/100-pt widths; share of tradable signals; portfolio path |
| EXP-005 | Which tenor? | expiry-day allowed; min DTE 1; min DTE 3; next expiry |

EXP-002..005 fix the expression chosen by EXP-001 evidence; that choice is recorded in EXPERIMENTS.md *before* they run.

## 9. Major risks and unknowns

1. **Capital feasibility (the biggest one, and it doesn't depend on data).** With NIFTY lot = 65 and IV ~13%, one lot
   costs roughly (Black-Scholes estimates, spot 25,000):

   | structure (calls) | 0 DTE (pm) | 1 DTE | 2 DTE | 4 DTE |
   |---|---|---|---|---|
   | ATM long call | Rs 2,450 | Rs 4,530 | Rs 6,480 | Rs 9,300 |
   | ATM / +50 spread | 1,300 | 1,460 | 1,520 | 1,580 |
   | ATM / +100 spread | 2,000 | 2,550 | 2,780 | 2,960 |
   | ATM / +200 spread | 2,420 | 3,840 | 4,580 | 5,200 |
   | +50 / +100 spread | 700 | 1,100 | 1,260 | 1,390 |

   At the 1% baseline (**Rs 1,000**) essentially only expiry-day OTM 50-point spreads fit one lot. Long options and every
   spread in the EXP-001 comparison are **rejected by the risk engine** at 1%. Research therefore measures edge in
   R-multiples on one lot (sizing-independent) and reports feasibility separately. If an edge is found, the options are:
   accept ~2-3% risk per trade (outside your stated framework), use 50-point spreads only, or add capital. **That is
   your decision once the evidence exists.**
2. **Costs vs R.** Fixed per-order fees are large relative to a Rs 1,000 R; small spreads need a sizeable gross edge just
   to break even.
3. **Spread data.** If historical bid/ask is unavailable, fill realism rests on estimates; the gate demands
   pessimistic-fill survival and live paper slippage must confirm it.
4. **Structural breaks** (lot sizes, expiry weekday, SEBI rule changes, STT) - possibly no long homogeneous sample.
5. **Multiple-testing risk.** Every grid point and variant is another chance for a false positive. Mitigations:
   plateau selection, walk-forward OOS, t-stat >= 2 OOS, and an experiment log that records *all* attempts.
6. **Intraday theta conventions.** The synthetic null test showed that pricing options on calendar time while variance
   accrues in trading time creates a fake long-gamma edge. Real option prices have their own intraday decay pattern;
   any "edge" in buying options intraday must be checked for this before it is believed.
7. **Constants** (independently reviewed 2026-10): STT history incl. 0.15% from 2026-04-01 and the post-Oct-2024 NSE
   charge are confirmed; lot sizes are keyed by contract expiry (NSE applies them per series). Still medium confidence:
   pre-Oct-2024 NSE transaction-charge history and the 2015 lot-size switch date - real data's own lot sizes override.
