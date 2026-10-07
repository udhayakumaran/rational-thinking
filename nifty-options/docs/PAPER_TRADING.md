# Paper trading

## Hard rule
V1 cannot trade real money: there is no order-routing code, no live-trading toggle and no path from a paper trade to a
broker order. `tests/test_no_live_trading.py` fails if order-routing calls appear anywhere. Broker APIs may be used for
**market data only**, with keys that have no order permission. Any live capability requires a separate, explicit
project decision.

## Promotion
Only strategies with verdict `PROMOTE_TO_PAPER` (or `FLAGGED` with a written justification in EXPERIMENTS.md) are
paper-traded. The exact config hash from the experiment is used; paper trading never tweaks parameters.

## Engine
`PaperEngine` (optlab/paper/engine.py) runs the same `TradingCore` as the backtester in portfolio mode, with one shared
RiskManager across strategies. On every 5-minute bar it:
1. recomputes signals on bars so far (causal) and keeps those stamped at the current bar,
2. fills pending decisions at the current snapshot's bid/ask (buys near ask, sells near bid; every leg pays slippage),
3. marks positions, evaluates exits, applies risk limits,
4. persists signals, rejected signals (with stage and reasons), orders, per-leg fills (price, mid, bid, ask, LTP,
   slippage, fees, estimated-spread flag), positions (with live marks and exit conditions), trades, account equity.

Each trade record carries: timestamps, spot, futures (when available), India VIX, expiry, strikes, per-leg prices,
bid/ask/LTP, IV and greeks, volume, OI, signal and features, regime, entry reason, structure, max loss/gain, account
risk, quantity, entry/exit fills, fees, slippage, theoretical (mid) P&L, net P&L, return on risk, exit reason.

## Running
* Rehearsal (no credentials needed): `python scripts/paper_replay.py --strategy-from reports/<ID>/summary.json --variant <v>`
* Live data: implement `MarketDataSource` for the chosen vendor (read-only methods), feed `LiveMarketData.ingest(...)`
  every bar close and call `engine.on_bar(ts)`. Not implemented until a vendor and credentials are chosen.
* Dashboard: `streamlit run optlab/dashboard/app.py`.

## Daily report
Written to `reports/paper/YYYY-MM-DD.md` at end of day: market (OHLC, range, largest move, regimes, VIX), signals and
rejections with reasons, entries/exits/open positions, gross/fees/slippage/net, expected vs observed behaviour,
anomalies (missing bars, exit-quote failures), and the standing conclusion that no change is made from one day.

## Backtest vs paper
`paper/compare.py` reports win rate, expectancy, average winner/loser, slippage, frequency and drawdown side by side,
and where the paper mean R falls in the bootstrap distribution of same-sized backtest samples (`paper_consistency`).
Fewer than 30 paper trades -> explicitly "not yet meaningful". Paper slippage materially above backtest slippage is a
reason to re-run the backtest with the observed slippage, not to keep trading.
