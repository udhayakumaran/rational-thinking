# Strategy research methodology

## Units
* **R** = the planned maximum theoretical loss of the whole structure *including estimated round-trip costs* for the
  lots traded. Every trade's result is reported as an R-multiple (net P&L / R). Research backtests trade **one lot** so
  R-expectancy is independent of account size; capital feasibility is measured separately.
* **Expectancy** E = P(win) x AvgWin - P(loss) x AvgLoss, reported in rupees/lot and in R. Win rate alone is never a
  decision criterion.

## Pipeline (per experiment variant)
1. **Grid** - every parameter combination is backtested once over the full sample (realistic fills, all costs).
2. **Train selection** - on the first 60% of sessions, choose the point with the best *robust value* =
   min(point expectancy, neighbourhood mean expectancy). A spike with poor neighbours loses to a plateau.
3. **Validation** (next 20%) and **Test** (final 20%) are reported for the chosen point. The test slice is not used to
   choose anything.
4. **Walk-forward**: 250-session train, 63-session test, rolling. Parameters are re-chosen in every train window with the
   same robust rule; the concatenation of test windows is the **OOS record** the gate evaluates.
5. **Fill stress**: optimistic, realistic, pessimistic fills on the chosen config.
6. **Rs 1L portfolio simulation** in `portfolio` mode: discrete lots, per-trade budget, open-risk cap, daily/weekly loss
   halts; all rejections are logged with reasons.
7. **Monte Carlo**: 5,000 block-bootstrap paths of OOS R-multiples at fixed-fractional risk -> distributions of final
   capital and max drawdown, P(-10%), P(-20%), P(DD >= 50% = "ruin"), expected worst losing streak.
8. **Gate** (`research/robustness.py`, version `gate-v1`).

## Promotion gate (gate-v1 defaults - to be re-set after inspecting real data)

| Check | Rule | Hard fail? |
|---|---|---|
| total sample | >= 150 trades (reject below 30) | <30 |
| OOS sample | >= 60 walk-forward OOS trades | yes |
| OOS expectancy | >= +0.05 R | yes |
| OOS t-stat | >= 2.0 | flag |
| OOS profit factor | >= 1.25 (net) | yes |
| OOS collapse | OOS E[R] >= 30% of in-sample E[R] | yes |
| profit concentration | top 10% of trades <= 60% of profit | flag |
| single-year dependence | best year <= 60% of profit | flag |
| parameter plateau | >= 60% of neighbours same-sign OOS expectancy | flag |
| pessimistic fills | E[R] > 0 at touch + slippage | yes |
| costs | net > 0 whenever theoretical > 0 | yes |
| regimes | >= 2 regimes with >= 20 trades and E[R] > 0 | flag |
| estimated spreads | <= 20% of trades filled on estimated quotes | flag |
| capital feasibility | >= 80% of trades fit one lot within 1% of Rs 1L | flag |
| portfolio drawdown | Rs 1L simulation max DD <= 15% | yes |
| Monte Carlo | P(max DD >= 20%) <= 10% | yes |

Verdicts: any hard fail -> **REJECT** (discard, do not rescue); flags only -> **FLAGGED** (needs a written argument
before paper); all pass -> **PROMOTE_TO_PAPER**. Changing a threshold requires an entry in EXPERIMENTS.md explaining
why, made *before* looking at the affected strategy's results.

## Robustness score (0-100, leaderboard)
OOS expectancy 20, OOS t-stat 20, PF 10, OOS sample 10, plateau 15, drawdown 10, regime consistency 5, paper
consistency 10 (0 until paper data exists). Total return is deliberately not an input.

## Rules of engagement
* Simple interpretable signals first. Filters are added **one at a time** (EXP-002) and kept only if they improve OOS
  expectancy without collapsing the sample.
* The same signal stream is used across expression variants so the comparison isolates the option structure.
* No machine learning in V1. A future model would estimate P(profitable | features) and must beat the rule baseline
  strictly out of sample.
* Every attempt is logged, including failures. The number of attempts is part of the evidence (multiple testing).
* Synthetic results (VAL-*) are never compared with real-data results (EXP-*).

## Regimes
Ex-ante (known at the open): trend = prior close vs SMA20 vs SMA50; volatility = today's VIX percentile vs trailing 252
sessions (<=30% low, >=70% high); dynamics = VIX vs prior 5-day mean (+/-10% expansion/contraction); tags = gap day
(|gap| >= 0.5%), expiry day. Results are sliced by regime, VIX bucket, direction, year and exit reason.
