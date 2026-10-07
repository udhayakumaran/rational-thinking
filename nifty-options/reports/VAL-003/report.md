# VAL-003 - Pipeline validation - can the gate PROMOTE? Positive control with Rs 10L capital (1% = Rs 10,000)

> **SYNTHETIC DATA - PIPELINE VALIDATION ONLY.** These numbers say nothing about the real NIFTY market and must not be compared with real-data experiments.

**Hypothesis.** Control: with a planted edge AND enough capital for one lot within 1% risk, the full gate should be passable. If it is not, the gate is mis-specified. Rs 10L is a test setting, not a recommendation.

**Data version:** `SYNTH-POSCTRL-c233a5ab0d`  |  **Walk-forward windows:** 8  |  **Runtime:** 120.3s

**Splits:** train 2023-01-02..2024-10-18, validation 2024-10-21..2025-05-27, test 2025-05-28..2025-12-31

## Variant comparison (identical signals, different option expression)

| variant | verdict | score | trades | OOS trades | OOS E[R] | OOS t | OOS PF | win% | avg win | avg loss | E[Rs]/lot | risk/lot | theta Rs/day | costs in R | theo E[R] | fits 1% budget | 1L port trades | 1L port maxDD | 1L share taken |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_long_atm | FLAGGED | 76.000 | 780 | 502 | 0.140 | 3.887 | 1.623 | 0.532 | 2,942.957 | 1,964.070 | 646.720 | 5,917.692 | -918.252 | 0.019 | 0.163 | 0.873 | 739 | 0.036 | 0.947 |
| C_itm50_to_otm100 | FLAGGED | 69.400 | 780 | 502 | 0.063 | 3.442 | 1.510 | 0.553 | 1,192.024 | 981.378 | 219.566 | 3,859.640 | -64.248 | 0.052 | 0.115 | 1.000 | 780 | 0.018 | 1.000 |


_E[R] = mean net P&L / planned max risk per trade (1 lot, realistic fills, all costs). 'theo E[R]' = mid-to-mid with no costs. 'fits 1% budget' = share of trades where one lot's max loss <= 1% of Rs 1L._


## Variant `A_long_atm`

`orb15:A_long_atm:long_opt[off+0]:SL0.7/EOD`  config `e0908ee56fc4`  chosen params: `{'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)}`

### Gate checks

| name | status | value | rule |
|---|---|---|---|
| sample_size_total | PASS | 780 | >= 150 |
| sample_size_oos | PASS | 502 | >= 60 |
| oos_expectancy_r | PASS | 0.140 | >= 0.05 |
| oos_tstat | PASS | 5.270 | >= 2.0 |
| oos_significance_multiple_testing | PASS | {'p': 0.0, 'p_adj': 0.0, 'n_tests': 18} | Sidak-adjusted p <= 0.05 over all variants x grid points tried |
| oos_profit_factor | PASS | 1.623 | >= 1.25 |
| oos_collapse | PASS | 0.795 | OOS/IS >= 0.3 |
| profit_concentration_top10pct | FLAG | 1.165 | <= 0.6 |
| best_year_share | PASS | 0.425 | <= 0.6 (needs >1 year) |
| estimated_spread_share | PASS | 0.000 | <= 0.2 (fills on unobserved quotes) |
| capital_feasibility | PASS | 0.873 | >= 0.8 of trades fit 1 lot in the per-trade budget |
| regime_consistency | PASS | 10 | >= 2 regimes with >= 20 trades and E[R] > 0 |
| pessimistic_fill_expectancy | PASS | 0.136 | > 0 under touch fills + slippage, on the same walk-forward OOS trades |
| edge_survives_costs | PASS | {'theoretical': 299738, 'net': 254493} | net > 0 whenever theoretical > 0 |
| parameter_plateau | PASS | 1.000 | share of neighbours with positive val+test expectancy >= 0.6 |
| portfolio_tradable | PASS | 0.947 | Rs 1L simulation with real limits takes >= 0.5 of research trades |
| portfolio_max_drawdown | PASS | 0.036 | <= 0.15 |
| mc_p_drawdown_20pct | PASS | 0.000 | <= 0.1 |


### Train / validation / test / walk-forward OOS

| period | trades | win_rate | expectancy | expectancy_r | expectancy_tstat | profit_factor | avg_winner | avg_loser | payoff_ratio | max_consec_losses |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 468 | 0.558 | 724.528 | 0.177 | 5.386 | 1.989 | 2,612.913 | 1,656.478 | 1.577 | 6 |
| validation | 157 | 0.522 | 700.244 | 0.145 | 2.287 | 1.670 | 3,342.457 | 2,188.577 | 1.527 | 4 |
| test | 155 | 0.465 | 357.575 | 0.045 | 1.070 | 1.264 | 3,684.381 | 2,528.329 | 1.457 | 7 |
| walk_forward_oos | 502 | 0.524 | 506.959 | 0.140 | 3.887 | 1.623 | 2,521.998 | 1,710.427 | 1.474 | 7 |


### Fill-model stress (test window)

| fill | trades | expectancy_r | profit_factor | total_pnl |
|---|---|---|---|---|
| optimistic | 155 | 0.051 | 1.302 | 62,368.240 |
| realistic | 155 | 0.045 | 1.264 | 55,424.115 |
| pessimistic | 155 | 0.040 | 1.237 | 50,237.638 |


### Rs 1,00,000 portfolio simulation (risk limits enforced)

| trades | total_return | cagr | max_drawdown_pct | sharpe | sortino | calmar | max_dd_duration |
|---|---|---|---|---|---|---|---|
| 739 | 1.617 | 0.363 | 0.036 | 3.890 | 8.738 | 10.090 | 76 |


Rejections by stage: `{'risk': 41}`; top reasons: `{'one_lot_risk_#_exceeds_budget_#': 41}`


### Monte Carlo (block bootstrap of OOS trades, discrete lots at the configured risk %, 1-year horizon)

Share of resampled trades that fit at least one lot: 95.7%

| sims | trades/path | median final | p5 final | p95 maxDD | P(-10%) | P(-20%) | P(DD>=20%) | P(DD>=50%) | E[max losing streak] |
|---|---|---|---|---|---|---|---|---|---|
| 5,000 | 251 | 1,341,764.824 | 1,183,784.344 | 0.047 | 0.000 | 0.000 | 0.000 | 0.000 | 6.806 |


Reference only - with divisible lots: median final 1,416,052, P(DD>=20%) 0.000.


_Monte Carlo assumes future trades resemble past ones; it measures luck, not model risk._


### By regime / volatility / direction / year


**by_regime**

| regime | trades | mean | win_rate | total |
|---|---|---|---|---|
| bear/high | 66 | 0.172 | 0.591 | 11.332 |
| bear/low | 80 | 0.178 | 0.512 | 14.215 |
| bear/normal | 83 | 0.093 | 0.530 | 7.705 |
| bear/unknown | 3 | 0.049 | 0.667 | 0.148 |
| bull/high | 57 | 0.065 | 0.491 | 3.720 |
| bull/low | 83 | 0.381 | 0.651 | 31.605 |
| bull/normal | 34 | 0.046 | 0.529 | 1.578 |
| range/high | 86 | 0.119 | 0.500 | 10.209 |
| range/low | 122 | 0.123 | 0.516 | 15.051 |
| range/normal | 109 | 0.101 | 0.486 | 11.001 |
| range/unknown | 7 | -0.074 | 0.286 | -0.520 |
| unknown/unknown | 50 | 0.126 | 0.560 | 6.289 |


**by_vol_regime**

| vol_regime | trades | mean | win_rate | total |
|---|---|---|---|---|
| high | 209 | 0.121 | 0.526 | 25.261 |
| low | 285 | 0.214 | 0.554 | 60.870 |
| normal | 226 | 0.090 | 0.509 | 20.284 |
| unknown | 60 | 0.099 | 0.533 | 5.917 |


**by_direction**

| direction | trades | mean | win_rate | total |
|---|---|---|---|---|
| BEARISH | 400 | 0.182 | 0.542 | 72.993 |
| BULLISH | 380 | 0.104 | 0.521 | 39.339 |


**by_year**

| year | trades | mean | win_rate | total |
|---|---|---|---|---|
| 2,023 | 259 | 0.154 | 0.548 | 39.836 |
| 2,024 | 261 | 0.179 | 0.540 | 46.720 |
| 2,025 | 260 | 0.099 | 0.508 | 25.777 |


**by_exit_reason**

| exit_reason | trades | mean | win_rate | total |
|---|---|---|---|---|
| eod_exit | 737 | 0.195 | 0.563 | 143.629 |
| stop_loss | 43 | -0.728 | 0.000 | -31.297 |


### Walk-forward windows

| k | train | test | params | is_trades | is_exp_r | oos_trades | oos_exp_r |
|---|---|---|---|---|---|---|---|
| 0 | 2023-01-02..2023-12-15 | 2023-12-18..2024-03-13 | {'signal_params.momentum_min_pct': np.float64(0.05), 'exits.stop_loss_pct': np.float64(0.7)} | 249 | 0.153 | 62 | 0.251 |
| 1 | 2023-03-30..2024-03-13 | 2024-03-14..2024-06-10 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 248 | 0.196 | 63 | 0.184 |
| 2 | 2023-06-27..2024-06-10 | 2024-06-11..2024-09-05 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 248 | 0.203 | 63 | 0.202 |
| 3 | 2023-09-22..2024-09-05 | 2024-09-06..2024-12-03 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 249 | 0.194 | 63 | 0.105 |
| 4 | 2023-12-20..2024-12-03 | 2024-12-04..2025-02-28 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 249 | 0.184 | 63 | 0.173 |
| 5 | 2024-03-18..2025-02-28 | 2025-03-03..2025-05-28 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 250 | 0.166 | 63 | 0.143 |
| 6 | 2024-06-13..2025-05-28 | 2025-05-29..2025-08-25 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 250 | 0.156 | 63 | 0.068 |
| 7 | 2024-09-10..2025-08-25 | 2025-08-26..2025-11-20 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 250 | 0.121 | 62 | -0.002 |


### Parameter sensitivity (validation+test period)

| signal_params.momentum_min_pct | exits.stop_loss_pct | trades | exp_r | tstat | win_rate | profit_factor | net_pnl |
|---|---|---|---|---|---|---|---|
| 0.000 | 0.300 | 312 | 0.085 | 2.663 | 0.433 | 1.408 | 146,664.334 |
| 0.000 | 0.500 | 312 | 0.090 | 2.722 | 0.490 | 1.437 | 162,958.253 |
| 0.000 | 0.700 | 312 | 0.095 | 2.824 | 0.494 | 1.442 | 165,362.347 |
| 0.050 | 0.300 | 312 | 0.082 | 2.575 | 0.429 | 1.392 | 141,896.927 |
| 0.050 | 0.500 | 312 | 0.090 | 2.694 | 0.490 | 1.435 | 162,061.613 |
| 0.050 | 0.700 | 312 | 0.094 | 2.800 | 0.494 | 1.441 | 164,731.581 |
| 0.100 | 0.300 | 312 | 0.067 | 2.302 | 0.429 | 1.359 | 128,620.425 |
| 0.100 | 0.500 | 312 | 0.073 | 2.366 | 0.487 | 1.379 | 141,459.238 |
| 0.100 | 0.700 | 312 | 0.079 | 2.512 | 0.490 | 1.390 | 145,525.978 |


## Variant `C_itm50_to_otm100`

`orb15:C_itm50_to_otm100:debit_spread[off-1,w150]:SL0.7/EOD`  config `92fbae2681b7`  chosen params: `{'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)}`

### Gate checks

| name | status | value | rule |
|---|---|---|---|
| sample_size_total | PASS | 780 | >= 150 |
| sample_size_oos | PASS | 502 | >= 60 |
| oos_expectancy_r | PASS | 0.062 | >= 0.05 |
| oos_tstat | PASS | 3.850 | >= 2.0 |
| oos_significance_multiple_testing | PASS | {'p': 0.0001, 'p_adj': 0.001, 'n_tests': 18} | Sidak-adjusted p <= 0.05 over all variants x grid points tried |
| oos_profit_factor | PASS | 1.510 | >= 1.25 |
| oos_collapse | PASS | 0.814 | OOS/IS >= 0.3 |
| profit_concentration_top10pct | FLAG | 1.317 | <= 0.6 |
| best_year_share | PASS | 0.340 | <= 0.6 (needs >1 year) |
| estimated_spread_share | PASS | 0.000 | <= 0.2 (fills on unobserved quotes) |
| capital_feasibility | PASS | 1.000 | >= 0.8 of trades fit 1 lot in the per-trade budget |
| regime_consistency | PASS | 10 | >= 2 regimes with >= 20 trades and E[R] > 0 |
| pessimistic_fill_expectancy | PASS | 0.051 | > 0 under touch fills + slippage, on the same walk-forward OOS trades |
| edge_survives_costs | PASS | {'theoretical': 200729, 'net': 112259} | net > 0 whenever theoretical > 0 |
| parameter_plateau | PASS | 1.000 | share of neighbours with positive val+test expectancy >= 0.6 |
| portfolio_tradable | PASS | 1.000 | Rs 1L simulation with real limits takes >= 0.5 of research trades |
| portfolio_max_drawdown | PASS | 0.018 | <= 0.15 |
| mc_p_drawdown_20pct | PASS | 0.000 | <= 0.1 |


### Train / validation / test / walk-forward OOS

| period | trades | win_rate | expectancy | expectancy_r | expectancy_tstat | profit_factor | avg_winner | avg_loser | payoff_ratio | max_consec_losses |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 468 | 0.573 | 230.198 | 0.077 | 4.363 | 1.682 | 991.750 | 790.281 | 1.255 | 6 |
| validation | 157 | 0.554 | 328.759 | 0.067 | 2.338 | 1.646 | 1,512.213 | 1,142.106 | 1.324 | 3 |
| test | 155 | 0.490 | 76.860 | 0.016 | 0.542 | 1.114 | 1,531.720 | 1,322.752 | 1.158 | 6 |
| walk_forward_oos | 502 | 0.548 | 223.624 | 0.063 | 3.442 | 1.510 | 1,209.048 | 970.171 | 1.246 | 6 |


### Fill-model stress (test window)

| fill | trades | expectancy_r | profit_factor | total_pnl |
|---|---|---|---|---|
| optimistic | 155 | 0.033 | 1.256 | 25,309.613 |
| realistic | 155 | 0.016 | 1.114 | 11,913.335 |
| pessimistic | 155 | 0.004 | 1.018 | 2,003.886 |


### Rs 1,00,000 portfolio simulation (risk limits enforced)

| trades | total_return | cagr | max_drawdown_pct | sharpe | sortino | calmar | max_dd_duration |
|---|---|---|---|---|---|---|---|
| 780 | 0.775 | 0.203 | 0.018 | 3.699 | 6.739 | 11.174 | 73 |


Rejections by stage: `{}`; top reasons: `{}`


### Monte Carlo (block bootstrap of OOS trades, discrete lots at the configured risk %, 1-year horizon)

Share of resampled trades that fit at least one lot: 100.0%

| sims | trades/path | median final | p5 final | p95 maxDD | P(-10%) | P(-20%) | P(DD>=20%) | P(DD>=50%) | E[max losing streak] |
|---|---|---|---|---|---|---|---|---|---|
| 5,000 | 251 | 1,137,941.639 | 1,049,324.928 | 0.042 | 0.000 | 0.000 | 0.000 | 0.000 | 6.330 |


Reference only - with divisible lots: median final 1,167,841, P(DD>=20%) 0.000.


_Monte Carlo assumes future trades resemble past ones; it measures luck, not model risk._


### By regime / volatility / direction / year


**by_regime**

| regime | trades | mean | win_rate | total |
|---|---|---|---|---|
| bear/high | 66 | 0.084 | 0.591 | 5.557 |
| bear/low | 80 | 0.081 | 0.537 | 6.456 |
| bear/normal | 83 | 0.035 | 0.566 | 2.888 |
| bear/unknown | 3 | 0.055 | 0.667 | 0.166 |
| bull/high | 57 | 0.017 | 0.526 | 0.963 |
| bull/low | 83 | 0.209 | 0.675 | 17.320 |
| bull/normal | 34 | 0.002 | 0.500 | 0.053 |
| range/high | 86 | 0.040 | 0.523 | 3.408 |
| range/low | 122 | 0.051 | 0.525 | 6.212 |
| range/normal | 109 | 0.042 | 0.523 | 4.628 |
| range/unknown | 7 | -0.134 | 0.286 | -0.940 |
| unknown/unknown | 50 | 0.045 | 0.580 | 2.267 |


**by_vol_regime**

| vol_regime | trades | mean | win_rate | total |
|---|---|---|---|---|
| high | 209 | 0.048 | 0.545 | 9.929 |
| low | 285 | 0.105 | 0.572 | 29.989 |
| normal | 226 | 0.033 | 0.535 | 7.568 |
| unknown | 60 | 0.025 | 0.550 | 1.493 |


**by_direction**

| direction | trades | mean | win_rate | total |
|---|---|---|---|---|
| BEARISH | 400 | 0.090 | 0.560 | 35.808 |
| BULLISH | 380 | 0.035 | 0.545 | 13.171 |


**by_year**

| year | trades | mean | win_rate | total |
|---|---|---|---|---|
| 2,023 | 259 | 0.065 | 0.568 | 16.843 |
| 2,024 | 261 | 0.077 | 0.559 | 20.213 |
| 2,025 | 260 | 0.046 | 0.531 | 11.923 |


**by_exit_reason**

| exit_reason | trades | mean | win_rate | total |
|---|---|---|---|---|
| eod_exit | 766 | 0.077 | 0.563 | 59.170 |
| stop_loss | 14 | -0.728 | 0.000 | -10.191 |


### Walk-forward windows

| k | train | test | params | is_trades | is_exp_r | oos_trades | oos_exp_r |
|---|---|---|---|---|---|---|---|
| 0 | 2023-01-02..2023-12-15 | 2023-12-18..2024-03-13 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 249 | 0.064 | 62 | 0.134 |
| 1 | 2023-03-30..2024-03-13 | 2024-03-14..2024-06-10 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 248 | 0.092 | 63 | 0.089 |
| 2 | 2023-06-27..2024-06-10 | 2024-06-11..2024-09-05 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.5)} | 248 | 0.101 | 63 | 0.074 |
| 3 | 2023-09-22..2024-09-05 | 2024-09-06..2024-12-03 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.5)} | 249 | 0.089 | 63 | 0.011 |
| 4 | 2023-12-20..2024-12-03 | 2024-12-04..2025-02-28 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 249 | 0.078 | 63 | 0.092 |
| 5 | 2024-03-18..2025-02-28 | 2025-03-03..2025-05-28 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 250 | 0.069 | 63 | 0.065 |
| 6 | 2024-06-13..2025-05-28 | 2025-05-29..2025-08-25 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 250 | 0.064 | 63 | 0.034 |
| 7 | 2024-09-10..2025-08-25 | 2025-08-26..2025-11-20 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 250 | 0.051 | 62 | 0.002 |


### Parameter sensitivity (validation+test period)

| signal_params.momentum_min_pct | exits.stop_loss_pct | trades | exp_r | tstat | win_rate | profit_factor | net_pnl |
|---|---|---|---|---|---|---|---|
| 0.000 | 0.300 | 312 | 0.037 | 1.868 | 0.510 | 1.326 | 59,763.978 |
| 0.000 | 0.500 | 312 | 0.037 | 1.798 | 0.519 | 1.303 | 57,377.812 |
| 0.000 | 0.700 | 312 | 0.042 | 2.038 | 0.522 | 1.344 | 63,528.449 |
| 0.050 | 0.300 | 312 | 0.036 | 1.838 | 0.510 | 1.324 | 59,379.636 |
| 0.050 | 0.500 | 312 | 0.036 | 1.745 | 0.519 | 1.297 | 56,390.812 |
| 0.050 | 0.700 | 312 | 0.041 | 2.005 | 0.522 | 1.343 | 63,155.334 |
| 0.100 | 0.300 | 312 | 0.028 | 1.508 | 0.503 | 1.270 | 49,788.125 |
| 0.100 | 0.500 | 312 | 0.031 | 1.553 | 0.513 | 1.269 | 50,396.012 |
| 0.100 | 0.700 | 312 | 0.032 | 1.619 | 0.513 | 1.272 | 50,916.074 |
