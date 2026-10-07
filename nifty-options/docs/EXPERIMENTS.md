# Experiment log

Append-only. Each entry: ID, date, code version, data version, hypothesis, result, verdict, decision.
`VAL-*` = pipeline validation on SYNTHETIC data (no information about the real market).
`EXP-*` = real-data research (none run yet - waiting on a data source).
Full reports: `reports/<ID>/report.md` and `summary.json`; trade-level CSVs are regenerated locally.

---

## Validation series (2026-10-07)

Common design (= EXP-001 design): ORB15 signal (VWAP + 3-bar momentum), identical signal stream for all variants,
intraday (exit by 15:15), min DTE 1. Variants: **A** ATM long option, **B** ATM->+100 call/put spread,
**C** ITM50->OTM100 spread, **D** ATM->+300 spread. Grid: momentum threshold {0, 0.05, 0.10}% x stop {30, 50, 70}% of
debit (36 configurations counted in the multiple-testing correction). 783 synthetic sessions 2023-2025, 60/20/20 split,
250/63 walk-forward (8 windows), realistic fills, all costs. Gate `gate-v1`.

Recorded code versions: VAL-001/002 `c958d31-dirty` (audit fixes; "dirty" = run logs then tracked; cost schedules
before the math review, so pre-2024 STT/exchange rates slightly off - irrelevant to what these controls test);
VAL-003 `977b548-dirty` (after the math-review fixes; dirty = the new VAL-003 spec file).

### VAL-001 - negative control (driftless market, fairly priced options)
| variant | verdict | OOS trades | OOS E[R] | t | PF | mid-to-mid E[R] | costs+slippage in R |
|---|---|---|---|---|---|---|---|
| A long ATM | REJECT | 502 | -0.020 | -1.8 | 0.81 | -0.004 | 0.018 |
| B ATM/+100 | REJECT | 502 | -0.068 | -4.2 | 0.62 | +0.006 | 0.076 |
| C ITM50/OTM100 | REJECT | 502 | -0.042 | -2.9 | 0.72 | +0.011 | 0.050 |
| D ATM/+300 | REJECT | 403 | -0.054 | -3.0 | 0.68 | -0.004 | 0.035 |

**Result: pass.** Mid-to-mid expectancy ~0 (no look-ahead, no P&L leakage); net expectancy = minus costs. Every variant
rejected on expectancy, PF, significance and fills. An earlier run of this control exposed a real modelling bug (options
priced on calendar time while variance accrued in trading time -> fake long-gamma edge); fixed before these runs.

### VAL-002 - positive control (planted continuation after an ORB break, 0.04 sigma/bar), Rs 1L at 1%
| variant | verdict | OOS E[R] | t | PF | mid-to-mid E[R] | costs in R | risk/lot | fits Rs 1,000 | Rs 1L trades |
|---|---|---|---|---|---|---|---|---|---|
| A long ATM | REJECT | +0.141 | 3.9 | 1.63 | 0.164 | 0.019 | Rs 5,946 | 0% | 0 |
| B ATM/+100 | REJECT | +0.048 | 2.3 | 1.31 | 0.124 | 0.078 | Rs 2,402 | 2% | 17 |
| C ITM50/OTM100 | REJECT | +0.063 | 3.5 | 1.51 | 0.115 | 0.051 | Rs 3,885 | 0% | 0 |
| D ATM/+300 | REJECT | +0.070 | 2.3 | 1.38 | 0.124 | 0.036 | Rs 5,065 | 0% | 0 |

**Result: pass.** The planted edge is detected in every expression. A, C, D fail ONLY `portfolio_tradable` - one lot
never fits a Rs 1,000 risk budget. B additionally fails because costs consume 0.078R of its 0.124R gross edge, leaving
E[R] below the 0.05 threshold and not significant after correcting for 36 tries.

### VAL-003 - can the gate promote at all? Positive control with Rs 10L (1% = Rs 10,000)
| variant | verdict | OOS E[R] | t | Rs 10L max DD | MC P(DD>=20%) | remaining flag |
|---|---|---|---|---|---|---|
| A long ATM | FLAGGED (score 76) | +0.140 | 3.9 | 3.6% | 0.00 | profit concentration |
| C ITM50/OTM100 | FLAGGED (score 69) | +0.063 | 3.4 | 1.8% | 0.00 | profit concentration |

**Result: pass.** With adequate capital the gate is passable; only the profit-concentration flag remains (top 10% of
trades > 100% of net profit), which is inherent to low-win-rate, positive-skew payoffs and correctly demands a written
justification rather than an automatic reject.

### What the controls teach about the research question (mechanics only, not market evidence)
1. **Rs 1L at 1% risk cannot trade NIFTY option structures**: one lot of ATM long options cost ~Rs 6,000 of max risk,
   spreads Rs 2,400-5,000. This does not depend on the data and will hold on real data.
2. **Spreads pay more cost per unit of risk.** Two legs x (fees + half-spread) on a smaller debit: costs = 0.05-0.08R
   for 100-150-pt spreads vs 0.02R for the long option. A spread therefore needs a materially larger gross edge (in R)
   to survive - the "debit spreads are more efficient" hypothesis has a cost headwind to overcome.
3. **Spreads are fill-sensitive.** Under pessimistic (touch) fills, the positive-control spreads' test-window E[R]
   fell to ~0 (B -0.018, C +0.004) while the long option kept +0.04.
4. On real data the comparison may come out differently (theta, skew, real spreads); EXP-001 decides.

### Decisions
* Pipeline accepted as validated for running EXP-001 once real data is imported and passes the quality checks.
* Gate thresholds unchanged (`gate-v1`).
* EXP-002..005 keep the placeholder expression (B) until EXP-001 results exist; the choice will be logged here first.

---

## EXP-001 ... EXP-005
Registered as specs in `config/experiments/`, not run: no real data yet (`data_version: REPLACE_WITH_REAL_DATA_VERSION`).
