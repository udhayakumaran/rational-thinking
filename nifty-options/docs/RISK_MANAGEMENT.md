# Risk management

## Account
* Starting paper capital: **Rs 1,00,000**. Paper only.
* Risk per trade: **1% of current equity** (baseline); 0.5 / 1.5 / 2% are research variants (EXP-004).

## Hard limits (`risk/manager.py`, configured in `config/default.yaml`)
| Limit | Value | Behaviour |
|---|---|---|
| Max risk per trade | 1% of equity | lots = floor(budget / risk per lot); **0 lots -> trade rejected and logged**, never rounded up |
| Max open risk | 5% of equity | lots shrink to fit; none fit -> rejected |
| Max daily realized loss | 3% of start-of-day equity | no new positions for the rest of the day |
| Max weekly realized loss | 6% of start-of-week equity | no new positions until next ISO week |
| Max concurrent positions | 3 (portfolio), 1 per strategy | |
| Account ruin | equity <= 0 | halt |

## What "risk" means
Risk per lot = **exact maximum theoretical loss of the complete structure at expiry** (computed from the payoff, using
the simulated fill prices) x lot size + estimated entry and exit costs. Not margin. Not the stop-loss distance (stops can
gap through). Structures with unbounded loss are rejected (`undefined_risk_structure`). V1 never sells naked options,
never averages down, never martingales.

## Forbidden in V1 (enforced by design)
naked short calls/puts, undefined-risk straddles/strangles, martingale / doubling, averaging losers, revenge re-entry
(one position per strategy, signals capped per day), discretionary overrides (no UI control can change a strategy).

## The Rs 1 lakh problem
See `PHASE1_ASSESSMENT.md` section 9. At 1% risk the per-trade budget (Rs 1,000) is below the one-lot max loss of
almost every NIFTY debit structure at lot size 65. This will show up as large `exceeds_budget` rejection counts in every
portfolio simulation. It is a finding, not a bug, and it's your decision how to respond once edge evidence exists.
