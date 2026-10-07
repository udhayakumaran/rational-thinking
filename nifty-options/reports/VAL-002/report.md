# VAL-002 - Pipeline validation - EXP-001 design on SYNTHETIC POSITIVE CONTROL (planted ORB drift)

> **SYNTHETIC DATA - PIPELINE VALIDATION ONLY.** These numbers say nothing about the real NIFTY market and must not be compared with real-data experiments.

**Hypothesis.** Strong directional NIFTY moves (15-min opening-range breakout confirmed by VWAP and short-term momentum) may be expressed more efficiently through debit spreads than through naked long options.

**Data version:** `SYNTH-POSCTRL-c233a5ab0d`  |  **Walk-forward windows:** 8  |  **Runtime:** 276.2s

**Splits:** train 2023-01-02..2024-10-18, validation 2024-10-21..2025-05-27, test 2025-05-28..2025-12-31

## Variant comparison (identical signals, different option expression)

| variant | verdict | score | trades | OOS trades | OOS E[R] | OOS t | OOS PF | win% | avg win | avg loss | E[Rs]/lot | risk/lot | theta Rs/day | costs in R | theo E[R] | fits 1% budget | 1L port trades | 1L port maxDD | 1L share taken |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_long_atm | REJECT | 67.600 | 780 | 502 | 0.141 | 3.927 | 1.629 | 0.533 | 2,961.046 | 1,976.992 | 656.628 | 5,946.269 | -923.468 | 0.019 | 0.164 | 0.000 | 0 | -0.000 | 0.000 |
| B_atm_to_otm100 | REJECT | 64.300 | 780 | 502 | 0.048 | 2.248 | 1.308 | 0.510 | 811.626 | 658.775 | 91.506 | 2,402.292 | -89.537 | 0.078 | 0.124 | 0.017 | 17 | 0.007 | 0.022 |
| C_itm50_to_otm100 | REJECT | 60.200 | 780 | 502 | 0.063 | 3.460 | 1.511 | 0.555 | 1,198.341 | 991.713 | 224.048 | 3,885.196 | -65.459 | 0.051 | 0.115 | 0.000 | 0 | -0.000 | 0.000 |
| D_atm_wide300 | REJECT | 59.500 | 627 | 371 | 0.070 | 2.295 | 1.385 | 0.531 | 2,005.689 | 1,467.848 | 376.949 | 5,064.591 | -386.433 | 0.036 | 0.124 | 0.000 | 0 | -0.000 | 0.000 |


_E[R] = mean net P&L / planned max risk per trade (1 lot, realistic fills, all costs). 'theo E[R]' = mid-to-mid with no costs. 'fits 1% budget' = share of trades where one lot's max loss <= 1% of Rs 1L._


## Variant `A_long_atm`

`orb15:A_long_atm:long_opt[off+0]:SL0.7/EOD`  config `e0908ee56fc4`  chosen params: `{'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)}`

### Gate checks

| name | status | value | rule |
|---|---|---|---|
| sample_size_total | PASS | 780 | >= 150 |
| sample_size_oos | PASS | 502 | >= 60 |
| oos_expectancy_r | PASS | 0.141 | >= 0.05 |
| oos_tstat | PASS | 5.290 | >= 2.0 |
| oos_significance_multiple_testing | PASS | {'p': 0.0, 'p_adj': 0.0, 'n_tests': 36} | Sidak-adjusted p <= 0.05 over all variants x grid points tried |
| oos_profit_factor | PASS | 1.629 | >= 1.25 |
| oos_collapse | PASS | 0.796 | OOS/IS >= 0.3 |
| profit_concentration_top10pct | FLAG | 1.159 | <= 0.6 |
| best_year_share | PASS | 0.419 | <= 0.6 (needs >1 year) |
| estimated_spread_share | PASS | 0.000 | <= 0.2 (fills on unobserved quotes) |
| capital_feasibility | FLAG | 0.000 | >= 0.8 of trades fit 1 lot in the per-trade budget |
| regime_consistency | PASS | 10 | >= 2 regimes with >= 20 trades and E[R] > 0 |
| pessimistic_fill_expectancy | PASS | 0.136 | > 0 under touch fills + slippage, on the same walk-forward OOS trades |
| edge_survives_costs | PASS | {'theoretical': 304343, 'net': 259135} | net > 0 whenever theoretical > 0 |
| parameter_plateau | PASS | 1.000 | share of neighbours with positive val+test expectancy >= 0.6 |
| portfolio_tradable | FAIL | 0.000 | Rs 1L simulation with real limits takes >= 0.5 of research trades |


### Train / validation / test / walk-forward OOS

| period | trades | win_rate | expectancy | expectancy_r | expectancy_tstat | profit_factor | avg_winner | avg_loser | payoff_ratio | max_consec_losses |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 468 | 0.558 | 725.615 | 0.177 | 5.393 | 1.990 | 2,614.800 | 1,656.401 | 1.579 | 6 |
| validation | 157 | 0.529 | 729.920 | 0.146 | 2.351 | 1.687 | 3,391.520 | 2,255.389 | 1.504 | 3 |
| test | 155 | 0.465 | 374.095 | 0.045 | 1.102 | 1.276 | 3,719.945 | 2,528.329 | 1.471 | 7 |
| walk_forward_oos | 502 | 0.526 | 516.205 | 0.141 | 3.927 | 1.629 | 2,541.115 | 1,729.914 | 1.469 | 7 |


### Fill-model stress (test window)

| fill | trades | expectancy_r | profit_factor | total_pnl |
|---|---|---|---|---|
| optimistic | 155 | 0.051 | 1.314 | 64,945.335 |
| realistic | 155 | 0.045 | 1.276 | 57,984.724 |
| pessimistic | 155 | 0.040 | 1.249 | 52,783.759 |


### Rs 1,00,000 portfolio simulation (risk limits enforced)

| trades | total_return | cagr | max_drawdown_pct | sharpe | sortino | calmar | max_dd_duration |
|---|---|---|---|---|---|---|---|
| 0 | 0.000 | 0.000 | -0.000 | - | - | - | 0 |


Rejections by stage: `{'risk': 780}`; top reasons: `{'one_lot_risk_#_exceeds_budget_#': 780}`


### Monte Carlo (block bootstrap of OOS trades, discrete lots at the configured risk %, 1-year horizon)

Share of resampled trades that fit at least one lot: 0.0%

| sims | trades/path | median final | p5 final | p95 maxDD | P(-10%) | P(-20%) | P(DD>=20%) | P(DD>=50%) | E[max losing streak] |
|---|---|---|---|---|---|---|---|---|---|
| 5,000 | 251 | 100,000.000 | 100,000.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |


Reference only - with divisible lots: median final 141,787, P(DD>=20%) 0.000.


_Monte Carlo assumes future trades resemble past ones; it measures luck, not model risk._


### By regime / volatility / direction / year


**by_regime**

| regime | trades | mean | win_rate | total |
|---|---|---|---|---|
| bear/high | 66 | 0.172 | 0.591 | 11.349 |
| bear/low | 80 | 0.178 | 0.512 | 14.256 |
| bear/normal | 83 | 0.093 | 0.530 | 7.726 |
| bear/unknown | 3 | 0.050 | 0.667 | 0.149 |
| bull/high | 57 | 0.065 | 0.491 | 3.724 |
| bull/low | 83 | 0.381 | 0.651 | 31.625 |
| bull/normal | 34 | 0.048 | 0.529 | 1.637 |
| range/high | 86 | 0.119 | 0.500 | 10.219 |
| range/low | 122 | 0.124 | 0.516 | 15.133 |
| range/normal | 109 | 0.101 | 0.495 | 11.052 |
| range/unknown | 7 | -0.074 | 0.286 | -0.519 |
| unknown/unknown | 50 | 0.126 | 0.560 | 6.302 |


**by_vol_regime**

| vol_regime | trades | mean | win_rate | total |
|---|---|---|---|---|
| high | 209 | 0.121 | 0.526 | 25.292 |
| low | 285 | 0.214 | 0.554 | 61.014 |
| normal | 226 | 0.090 | 0.513 | 20.415 |
| unknown | 60 | 0.099 | 0.533 | 5.932 |


**by_direction**

| direction | trades | mean | win_rate | total |
|---|---|---|---|---|
| BEARISH | 400 | 0.183 | 0.542 | 73.156 |
| BULLISH | 380 | 0.104 | 0.524 | 39.497 |


**by_year**

| year | trades | mean | win_rate | total |
|---|---|---|---|---|
| 2,023 | 259 | 0.154 | 0.548 | 39.934 |
| 2,024 | 261 | 0.180 | 0.544 | 46.940 |
| 2,025 | 260 | 0.099 | 0.508 | 25.778 |


**by_exit_reason**

| exit_reason | trades | mean | win_rate | total |
|---|---|---|---|---|
| eod_exit | 737 | 0.195 | 0.564 | 143.950 |
| stop_loss | 43 | -0.728 | 0.000 | -31.297 |


### Walk-forward windows

| k | train | test | params | is_trades | is_exp_r | oos_trades | oos_exp_r |
|---|---|---|---|---|---|---|---|
| 0 | 2023-01-02..2023-12-15 | 2023-12-18..2024-03-13 | {'signal_params.momentum_min_pct': np.float64(0.05), 'exits.stop_loss_pct': np.float64(0.7)} | 249 | 0.153 | 62 | 0.251 |
| 1 | 2023-03-30..2024-03-13 | 2024-03-14..2024-06-10 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 248 | 0.197 | 63 | 0.185 |
| 2 | 2023-06-27..2024-06-10 | 2024-06-11..2024-09-05 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 248 | 0.203 | 63 | 0.202 |
| 3 | 2023-09-22..2024-09-05 | 2024-09-06..2024-12-03 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 249 | 0.194 | 63 | 0.107 |
| 4 | 2023-12-20..2024-12-03 | 2024-12-04..2025-02-28 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 249 | 0.185 | 63 | 0.173 |
| 5 | 2024-03-18..2025-02-28 | 2025-03-03..2025-05-28 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 250 | 0.166 | 63 | 0.143 |
| 6 | 2024-06-13..2025-05-28 | 2025-05-29..2025-08-25 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 250 | 0.157 | 63 | 0.068 |
| 7 | 2024-09-10..2025-08-25 | 2025-08-26..2025-11-20 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 250 | 0.121 | 62 | -0.002 |


### Parameter sensitivity (validation+test period)

| signal_params.momentum_min_pct | exits.stop_loss_pct | trades | exp_r | tstat | win_rate | profit_factor | net_pnl |
|---|---|---|---|---|---|---|---|
| 0.000 | 0.300 | 312 | 0.085 | 2.676 | 0.436 | 1.425 | 153,919.084 |
| 0.000 | 0.500 | 312 | 0.091 | 2.734 | 0.494 | 1.451 | 169,556.433 |
| 0.000 | 0.700 | 312 | 0.096 | 2.836 | 0.497 | 1.458 | 172,582.147 |
| 0.050 | 0.300 | 312 | 0.082 | 2.588 | 0.433 | 1.409 | 149,151.677 |
| 0.050 | 0.500 | 312 | 0.090 | 2.705 | 0.494 | 1.449 | 168,659.793 |
| 0.050 | 0.700 | 312 | 0.095 | 2.811 | 0.497 | 1.457 | 171,951.381 |
| 0.100 | 0.300 | 312 | 0.068 | 2.315 | 0.433 | 1.376 | 135,875.175 |
| 0.100 | 0.500 | 312 | 0.073 | 2.378 | 0.490 | 1.393 | 148,057.419 |
| 0.100 | 0.700 | 312 | 0.079 | 2.525 | 0.494 | 1.406 | 152,745.777 |


## Variant `B_atm_to_otm100`

`orb15:B_atm_to_otm100:debit_spread[off+0,w100]:SL0.7/EOD`  config `3e72d3c28926`  chosen params: `{'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)}`

### Gate checks

| name | status | value | rule |
|---|---|---|---|
| sample_size_total | PASS | 780 | >= 150 |
| sample_size_oos | PASS | 502 | >= 60 |
| oos_expectancy_r | FAIL | 0.048 | >= 0.05 |
| oos_tstat | PASS | 2.650 | >= 2.0 |
| oos_significance_multiple_testing | FAIL | {'p': 0.004, 'p_adj': 0.1344, 'n_tests': 36} | Sidak-adjusted p <= 0.05 over all variants x grid points tried |
| oos_profit_factor | PASS | 1.308 | >= 1.25 |
| oos_collapse | PASS | 0.846 | OOS/IS >= 0.3 |
| profit_concentration_top10pct | FLAG | 2.119 | <= 0.6 |
| best_year_share | PASS | 0.394 | <= 0.6 (needs >1 year) |
| estimated_spread_share | PASS | 0.000 | <= 0.2 (fills on unobserved quotes) |
| capital_feasibility | FLAG | 0.017 | >= 0.8 of trades fit 1 lot in the per-trade budget |
| regime_consistency | PASS | 8 | >= 2 regimes with >= 20 trades and E[R] > 0 |
| pessimistic_fill_expectancy | PASS | 0.033 | > 0 under touch fills + slippage, on the same walk-forward OOS trades |
| edge_survives_costs | PASS | {'theoretical': 132938, 'net': 49616} | net > 0 whenever theoretical > 0 |
| parameter_plateau | PASS | 1.000 | share of neighbours with positive val+test expectancy >= 0.6 |
| portfolio_tradable | FAIL | 0.022 | Rs 1L simulation with real limits takes >= 0.5 of research trades |
| portfolio_max_drawdown | PASS | 0.007 | <= 0.15 |
| mc_p_drawdown_20pct | PASS | 0.000 | <= 0.1 |


### Train / validation / test / walk-forward OOS

| period | trades | win_rate | expectancy | expectancy_r | expectancy_tstat | profit_factor | avg_winner | avg_loser | payoff_ratio | max_consec_losses |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 468 | 0.524 | 101.769 | 0.057 | 2.869 | 1.407 | 672.468 | 525.231 | 1.280 | 6 |
| validation | 157 | 0.510 | 164.857 | 0.058 | 1.703 | 1.432 | 1,071.588 | 777.201 | 1.379 | 3 |
| test | 155 | 0.471 | -13.779 | -0.002 | -0.146 | 0.971 | 993.773 | 910.746 | 1.091 | 6 |
| walk_forward_oos | 502 | 0.504 | 98.837 | 0.048 | 2.248 | 1.308 | 832.041 | 646.144 | 1.288 | 6 |


### Fill-model stress (test window)

| fill | trades | expectancy_r | profit_factor | total_pnl |
|---|---|---|---|---|
| optimistic | 155 | 0.022 | 1.142 | 9,838.769 |
| realistic | 155 | -0.002 | 0.971 | -2,135.746 |
| pessimistic | 155 | -0.018 | 0.865 | -10,578.736 |


### Rs 1,00,000 portfolio simulation (risk limits enforced)

| trades | total_return | cagr | max_drawdown_pct | sharpe | sortino | calmar | max_dd_duration |
|---|---|---|---|---|---|---|---|
| 17 | 0.025 | 0.008 | 0.007 | 0.661 | 1.245 | 1.093 | 292 |


Rejections by stage: `{'risk': 763}`; top reasons: `{'one_lot_risk_#_exceeds_budget_#': 763}`


### Monte Carlo (block bootstrap of OOS trades, discrete lots at the configured risk %, 1-year horizon)

Share of resampled trades that fit at least one lot: 3.2%

| sims | trades/path | median final | p5 final | p95 maxDD | P(-10%) | P(-20%) | P(DD>=20%) | P(DD>=50%) | E[max losing streak] |
|---|---|---|---|---|---|---|---|---|---|
| 5,000 | 251 | 100,735.229 | 98,450.966 | 0.021 | 0.000 | 0.000 | 0.000 | 0.000 | 2.026 |


Reference only - with divisible lots: median final 112,636, P(DD>=20%) 0.000.


_Monte Carlo assumes future trades resemble past ones; it measures luck, not model risk._


### By regime / volatility / direction / year


**by_regime**

| regime | trades | mean | win_rate | total |
|---|---|---|---|---|
| bear/high | 66 | 0.058 | 0.561 | 3.811 |
| bear/low | 80 | 0.069 | 0.500 | 5.512 |
| bear/normal | 83 | 0.018 | 0.506 | 1.506 |
| bear/unknown | 3 | 0.029 | 0.667 | 0.086 |
| bull/high | 57 | -0.009 | 0.474 | -0.527 |
| bull/low | 83 | 0.225 | 0.651 | 18.707 |
| bull/normal | 34 | -0.023 | 0.500 | -0.767 |
| range/high | 86 | 0.017 | 0.477 | 1.423 |
| range/low | 122 | 0.030 | 0.484 | 3.634 |
| range/normal | 109 | 0.020 | 0.477 | 2.216 |
| range/unknown | 7 | -0.160 | 0.286 | -1.119 |
| unknown/unknown | 50 | 0.021 | 0.500 | 1.068 |


**by_vol_regime**

| vol_regime | trades | mean | win_rate | total |
|---|---|---|---|---|
| high | 209 | 0.023 | 0.502 | 4.706 |
| low | 285 | 0.098 | 0.537 | 27.852 |
| normal | 226 | 0.013 | 0.491 | 2.955 |
| unknown | 60 | 0.001 | 0.483 | 0.035 |


**by_direction**

| direction | trades | mean | win_rate | total |
|---|---|---|---|---|
| BEARISH | 400 | 0.072 | 0.515 | 28.658 |
| BULLISH | 380 | 0.018 | 0.505 | 6.891 |


**by_year**

| year | trades | mean | win_rate | total |
|---|---|---|---|---|
| 2,023 | 259 | 0.046 | 0.521 | 11.793 |
| 2,024 | 261 | 0.058 | 0.510 | 15.105 |
| 2,025 | 260 | 0.033 | 0.500 | 8.652 |


**by_exit_reason**

| exit_reason | trades | mean | win_rate | total |
|---|---|---|---|---|
| eod_exit | 756 | 0.071 | 0.526 | 53.404 |
| stop_loss | 24 | -0.744 | 0.000 | -17.854 |


### Walk-forward windows

| k | train | test | params | is_trades | is_exp_r | oos_trades | oos_exp_r |
|---|---|---|---|---|---|---|---|
| 0 | 2023-01-02..2023-12-15 | 2023-12-18..2024-03-13 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 249 | 0.044 | 62 | 0.131 |
| 1 | 2023-03-30..2024-03-13 | 2024-03-14..2024-06-10 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 248 | 0.078 | 63 | 0.071 |
| 2 | 2023-06-27..2024-06-10 | 2024-06-11..2024-09-05 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 248 | 0.086 | 63 | 0.050 |
| 3 | 2023-09-22..2024-09-05 | 2024-09-06..2024-12-03 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 249 | 0.071 | 63 | -0.009 |
| 4 | 2023-12-20..2024-12-03 | 2024-12-04..2025-02-28 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 249 | 0.058 | 63 | 0.089 |
| 5 | 2024-03-18..2025-02-28 | 2025-03-03..2025-05-28 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 250 | 0.050 | 63 | 0.053 |
| 6 | 2024-06-13..2025-05-28 | 2025-05-29..2025-08-25 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 250 | 0.046 | 63 | 0.022 |
| 7 | 2024-09-10..2025-08-25 | 2025-08-26..2025-11-20 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 250 | 0.038 | 62 | -0.020 |


### Parameter sensitivity (validation+test period)

| signal_params.momentum_min_pct | exits.stop_loss_pct | trades | exp_r | tstat | win_rate | profit_factor | net_pnl |
|---|---|---|---|---|---|---|---|
| 0.000 | 0.300 | 312 | 0.025 | 1.117 | 0.474 | 1.177 | 23,175.382 |
| 0.000 | 0.500 | 312 | 0.025 | 1.066 | 0.487 | 1.151 | 20,686.563 |
| 0.000 | 0.700 | 312 | 0.028 | 1.210 | 0.490 | 1.177 | 23,746.791 |
| 0.050 | 0.300 | 312 | 0.023 | 1.063 | 0.474 | 1.172 | 22,472.004 |
| 0.050 | 0.500 | 312 | 0.024 | 1.018 | 0.487 | 1.146 | 20,086.545 |
| 0.050 | 0.700 | 312 | 0.027 | 1.178 | 0.490 | 1.175 | 23,498.460 |
| 0.100 | 0.300 | 312 | 0.013 | 0.633 | 0.471 | 1.118 | 15,602.066 |
| 0.100 | 0.500 | 312 | 0.014 | 0.634 | 0.484 | 1.100 | 13,788.771 |
| 0.100 | 0.700 | 312 | 0.015 | 0.698 | 0.484 | 1.110 | 14,969.835 |


## Variant `C_itm50_to_otm100`

`orb15:C_itm50_to_otm100:debit_spread[off-1,w150]:SL0.7/EOD`  config `92fbae2681b7`  chosen params: `{'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)}`

### Gate checks

| name | status | value | rule |
|---|---|---|---|
| sample_size_total | PASS | 780 | >= 150 |
| sample_size_oos | PASS | 502 | >= 60 |
| oos_expectancy_r | PASS | 0.063 | >= 0.05 |
| oos_tstat | PASS | 3.910 | >= 2.0 |
| oos_significance_multiple_testing | PASS | {'p': 0.0, 'p_adj': 0.0017, 'n_tests': 36} | Sidak-adjusted p <= 0.05 over all variants x grid points tried |
| oos_profit_factor | PASS | 1.511 | >= 1.25 |
| oos_collapse | PASS | 0.814 | OOS/IS >= 0.3 |
| profit_concentration_top10pct | FLAG | 1.300 | <= 0.6 |
| best_year_share | PASS | 0.345 | <= 0.6 (needs >1 year) |
| estimated_spread_share | PASS | 0.000 | <= 0.2 (fills on unobserved quotes) |
| capital_feasibility | FLAG | 0.000 | >= 0.8 of trades fit 1 lot in the per-trade budget |
| regime_consistency | PASS | 10 | >= 2 regimes with >= 20 trades and E[R] > 0 |
| pessimistic_fill_expectancy | PASS | 0.052 | > 0 under touch fills + slippage, on the same walk-forward OOS trades |
| edge_survives_costs | PASS | {'theoretical': 202194, 'net': 113772} | net > 0 whenever theoretical > 0 |
| parameter_plateau | PASS | 1.000 | share of neighbours with positive val+test expectancy >= 0.6 |
| portfolio_tradable | FAIL | 0.000 | Rs 1L simulation with real limits takes >= 0.5 of research trades |


### Train / validation / test / walk-forward OOS

| period | trades | win_rate | expectancy | expectancy_r | expectancy_tstat | profit_factor | avg_winner | avg_loser | payoff_ratio | max_consec_losses |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 468 | 0.577 | 233.065 | 0.078 | 4.415 | 1.692 | 987.931 | 796.299 | 1.241 | 6 |
| validation | 157 | 0.554 | 339.918 | 0.069 | 2.384 | 1.651 | 1,555.484 | 1,170.857 | 1.329 | 3 |
| test | 155 | 0.490 | 79.457 | 0.016 | 0.559 | 1.118 | 1,537.017 | 1,322.752 | 1.162 | 6 |
| walk_forward_oos | 502 | 0.548 | 226.637 | 0.063 | 3.460 | 1.511 | 1,223.800 | 981.381 | 1.247 | 6 |


### Fill-model stress (test window)

| fill | trades | expectancy_r | profit_factor | total_pnl |
|---|---|---|---|---|
| optimistic | 155 | 0.033 | 1.261 | 25,743.637 |
| realistic | 155 | 0.016 | 1.118 | 12,315.876 |
| pessimistic | 155 | 0.004 | 1.022 | 2,378.941 |


### Rs 1,00,000 portfolio simulation (risk limits enforced)

| trades | total_return | cagr | max_drawdown_pct | sharpe | sortino | calmar | max_dd_duration |
|---|---|---|---|---|---|---|---|
| 0 | 0.000 | 0.000 | -0.000 | - | - | - | 0 |


Rejections by stage: `{'risk': 780}`; top reasons: `{'one_lot_risk_#_exceeds_budget_#': 780}`


### Monte Carlo (block bootstrap of OOS trades, discrete lots at the configured risk %, 1-year horizon)

Share of resampled trades that fit at least one lot: 0.0%

| sims | trades/path | median final | p5 final | p95 maxDD | P(-10%) | P(-20%) | P(DD>=20%) | P(DD>=50%) | E[max losing streak] |
|---|---|---|---|---|---|---|---|---|---|
| 5,000 | 251 | 100,000.000 | 100,000.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |


Reference only - with divisible lots: median final 117,047, P(DD>=20%) 0.000.


_Monte Carlo assumes future trades resemble past ones; it measures luck, not model risk._


### By regime / volatility / direction / year


**by_regime**

| regime | trades | mean | win_rate | total |
|---|---|---|---|---|
| bear/high | 66 | 0.085 | 0.591 | 5.596 |
| bear/low | 80 | 0.082 | 0.537 | 6.560 |
| bear/normal | 83 | 0.035 | 0.566 | 2.938 |
| bear/unknown | 3 | 0.056 | 0.667 | 0.169 |
| bull/high | 57 | 0.017 | 0.526 | 0.976 |
| bull/low | 83 | 0.209 | 0.675 | 17.358 |
| bull/normal | 34 | 0.005 | 0.500 | 0.177 |
| range/high | 86 | 0.040 | 0.535 | 3.439 |
| range/low | 122 | 0.052 | 0.533 | 6.372 |
| range/normal | 109 | 0.043 | 0.523 | 4.736 |
| range/unknown | 7 | -0.133 | 0.286 | -0.933 |
| unknown/unknown | 50 | 0.046 | 0.580 | 2.325 |


**by_vol_regime**

| vol_regime | trades | mean | win_rate | total |
|---|---|---|---|---|
| high | 209 | 0.048 | 0.550 | 10.012 |
| low | 285 | 0.106 | 0.575 | 30.291 |
| normal | 226 | 0.035 | 0.535 | 7.852 |
| unknown | 60 | 0.026 | 0.550 | 1.560 |


**by_direction**

| direction | trades | mean | win_rate | total |
|---|---|---|---|---|
| BEARISH | 400 | 0.090 | 0.565 | 36.186 |
| BULLISH | 380 | 0.036 | 0.545 | 13.529 |


**by_year**

| year | trades | mean | win_rate | total |
|---|---|---|---|---|
| 2,023 | 259 | 0.066 | 0.575 | 17.135 |
| 2,024 | 261 | 0.079 | 0.559 | 20.653 |
| 2,025 | 260 | 0.046 | 0.531 | 11.926 |


**by_exit_reason**

| exit_reason | trades | mean | win_rate | total |
|---|---|---|---|---|
| eod_exit | 766 | 0.078 | 0.565 | 59.907 |
| stop_loss | 14 | -0.728 | 0.000 | -10.192 |


### Walk-forward windows

| k | train | test | params | is_trades | is_exp_r | oos_trades | oos_exp_r |
|---|---|---|---|---|---|---|---|
| 0 | 2023-01-02..2023-12-15 | 2023-12-18..2024-03-13 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 249 | 0.065 | 62 | 0.135 |
| 1 | 2023-03-30..2024-03-13 | 2024-03-14..2024-06-10 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 248 | 0.094 | 63 | 0.091 |
| 2 | 2023-06-27..2024-06-10 | 2024-06-11..2024-09-05 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.5)} | 248 | 0.102 | 63 | 0.075 |
| 3 | 2023-09-22..2024-09-05 | 2024-09-06..2024-12-03 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.5)} | 249 | 0.090 | 63 | 0.015 |
| 4 | 2023-12-20..2024-12-03 | 2024-12-04..2025-02-28 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 249 | 0.080 | 63 | 0.092 |
| 5 | 2024-03-18..2025-02-28 | 2025-03-03..2025-05-28 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 250 | 0.071 | 63 | 0.065 |
| 6 | 2024-06-13..2025-05-28 | 2025-05-29..2025-08-25 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 250 | 0.065 | 63 | 0.034 |
| 7 | 2024-09-10..2025-08-25 | 2025-08-26..2025-11-20 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 250 | 0.052 | 62 | 0.002 |


### Parameter sensitivity (validation+test period)

| signal_params.momentum_min_pct | exits.stop_loss_pct | trades | exp_r | tstat | win_rate | profit_factor | net_pnl |
|---|---|---|---|---|---|---|---|
| 0.000 | 0.300 | 312 | 0.037 | 1.906 | 0.510 | 1.332 | 61,618.917 |
| 0.000 | 0.500 | 312 | 0.038 | 1.833 | 0.519 | 1.307 | 58,940.744 |
| 0.000 | 0.700 | 312 | 0.043 | 2.075 | 0.522 | 1.352 | 65,682.987 |
| 0.050 | 0.300 | 312 | 0.037 | 1.876 | 0.510 | 1.330 | 61,234.575 |
| 0.050 | 0.500 | 312 | 0.037 | 1.780 | 0.519 | 1.301 | 57,953.744 |
| 0.050 | 0.700 | 312 | 0.042 | 2.042 | 0.522 | 1.351 | 65,309.872 |
| 0.100 | 0.300 | 312 | 0.029 | 1.547 | 0.503 | 1.277 | 51,643.064 |
| 0.100 | 0.500 | 312 | 0.031 | 1.590 | 0.513 | 1.273 | 51,958.944 |
| 0.100 | 0.700 | 312 | 0.033 | 1.658 | 0.513 | 1.281 | 53,070.612 |


## Variant `D_atm_wide300`

`orb15:D_atm_wide300:debit_spread[off+0,w300]:SL0.7/EOD`  config `82cd4f9e615a`  chosen params: `{'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)}`

### Gate checks

| name | status | value | rule |
|---|---|---|---|
| sample_size_total | PASS | 627 | >= 150 |
| sample_size_oos | PASS | 371 | >= 60 |
| oos_expectancy_r | PASS | 0.070 | >= 0.05 |
| oos_tstat | PASS | 3.040 | >= 2.0 |
| oos_significance_multiple_testing | PASS | {'p': 0.0012, 'p_adj': 0.0421, 'n_tests': 36} | Sidak-adjusted p <= 0.05 over all variants x grid points tried |
| oos_profit_factor | PASS | 1.385 | >= 1.25 |
| oos_collapse | PASS | 0.614 | OOS/IS >= 0.3 |
| profit_concentration_top10pct | FLAG | 1.309 | <= 0.6 |
| best_year_share | PASS | 0.450 | <= 0.6 (needs >1 year) |
| estimated_spread_share | PASS | 0.000 | <= 0.2 (fills on unobserved quotes) |
| capital_feasibility | FLAG | 0.000 | >= 0.8 of trades fit 1 lot in the per-trade budget |
| regime_consistency | PASS | 10 | >= 2 regimes with >= 20 trades and E[R] > 0 |
| pessimistic_fill_expectancy | PASS | 0.064 | > 0 under touch fills + slippage, on the same walk-forward OOS trades |
| edge_survives_costs | PASS | {'theoretical': 156504, 'net': 98020} | net > 0 whenever theoretical > 0 |
| parameter_plateau | PASS | 1.000 | share of neighbours with positive val+test expectancy >= 0.6 |
| portfolio_tradable | FAIL | 0.000 | Rs 1L simulation with real limits takes >= 0.5 of research trades |


### Train / validation / test / walk-forward OOS

| period | trades | win_rate | expectancy | expectancy_r | expectancy_tstat | profit_factor | avg_winner | avg_loser | payoff_ratio | max_consec_losses |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 385 | 0.556 | 416.142 | 0.115 | 4.295 | 1.776 | 1,713.003 | 1,206.830 | 1.419 | 6 |
| validation | 117 | 0.521 | 478.704 | 0.079 | 1.815 | 1.572 | 2,522.658 | 1,747.746 | 1.443 | 4 |
| test | 125 | 0.464 | 160.990 | 0.017 | 0.641 | 1.158 | 2,541.888 | 1,900.087 | 1.338 | 5 |
| walk_forward_oos | 371 | 0.501 | 264.206 | 0.070 | 2.295 | 1.385 | 1,896.166 | 1,376.576 | 1.377 | 5 |


### Fill-model stress (test window)

| fill | trades | expectancy_r | profit_factor | total_pnl |
|---|---|---|---|---|
| optimistic | 125 | 0.027 | 1.233 | 28,730.592 |
| realistic | 125 | 0.017 | 1.158 | 20,123.689 |
| pessimistic | 125 | 0.011 | 1.110 | 14,287.421 |


### Rs 1,00,000 portfolio simulation (risk limits enforced)

| trades | total_return | cagr | max_drawdown_pct | sharpe | sortino | calmar | max_dd_duration |
|---|---|---|---|---|---|---|---|
| 0 | 0.000 | 0.000 | -0.000 | - | - | - | 0 |


Rejections by stage: `{'risk': 627, 'liquidity': 144, 'pricing': 9}`; top reasons: `{'one_lot_risk_#_exceeds_budget_#': 627, 'wide_spread:NIFTY#PE:#.#': 81, 'wide_spread:NIFTY#CE:#.#': 63, 'premium_below_min:NIFTY#PE:#.#': 50, 'premium_below_min:NIFTY#CE:#.#': 36}`


### Monte Carlo (block bootstrap of OOS trades, discrete lots at the configured risk %, 1-year horizon)

Share of resampled trades that fit at least one lot: 0.0%

| sims | trades/path | median final | p5 final | p95 maxDD | P(-10%) | P(-20%) | P(DD>=20%) | P(DD>=50%) | E[max losing streak] |
|---|---|---|---|---|---|---|---|---|---|
| 5,000 | 202 | 100,000.000 | 100,000.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |


Reference only - with divisible lots: median final 115,300, P(DD>=20%) 0.000.


_Monte Carlo assumes future trades resemble past ones; it measures luck, not model risk._


### By regime / volatility / direction / year


**by_regime**

| regime | trades | mean | win_rate | total |
|---|---|---|---|---|
| bear/high | 61 | 0.132 | 0.590 | 8.052 |
| bear/low | 63 | 0.111 | 0.524 | 6.993 |
| bear/normal | 65 | 0.052 | 0.508 | 3.363 |
| bear/unknown | 3 | 0.072 | 0.667 | 0.215 |
| bull/high | 55 | 0.056 | 0.545 | 3.060 |
| bull/low | 45 | 0.167 | 0.600 | 7.530 |
| bull/normal | 28 | 0.104 | 0.536 | 2.918 |
| range/high | 83 | 0.086 | 0.530 | 7.173 |
| range/low | 78 | 0.102 | 0.538 | 7.964 |
| range/normal | 89 | 0.044 | 0.438 | 3.940 |
| range/unknown | 7 | -0.102 | 0.286 | -0.712 |
| unknown/unknown | 50 | 0.099 | 0.600 | 4.954 |


**by_vol_regime**

| vol_regime | trades | mean | win_rate | total |
|---|---|---|---|---|
| high | 199 | 0.092 | 0.553 | 18.285 |
| low | 186 | 0.121 | 0.548 | 22.488 |
| normal | 182 | 0.056 | 0.478 | 10.221 |
| unknown | 60 | 0.074 | 0.567 | 4.457 |


**by_direction**

| direction | trades | mean | win_rate | total |
|---|---|---|---|---|
| BEARISH | 314 | 0.126 | 0.541 | 39.663 |
| BULLISH | 313 | 0.050 | 0.521 | 15.787 |


**by_year**

| year | trades | mean | win_rate | total |
|---|---|---|---|---|
| 2,023 | 231 | 0.106 | 0.563 | 24.535 |
| 2,024 | 186 | 0.108 | 0.522 | 20.068 |
| 2,025 | 210 | 0.052 | 0.505 | 10.848 |


**by_exit_reason**

| exit_reason | trades | mean | win_rate | total |
|---|---|---|---|---|
| eod_exit | 612 | 0.108 | 0.544 | 66.206 |
| stop_loss | 15 | -0.717 | 0.000 | -10.755 |


### Walk-forward windows

| k | train | test | params | is_trades | is_exp_r | oos_trades | oos_exp_r |
|---|---|---|---|---|---|---|---|
| 0 | 2023-01-02..2023-12-15 | 2023-12-18..2024-03-13 | {'signal_params.momentum_min_pct': np.float64(0.1), 'exits.stop_loss_pct': np.float64(0.7)} | 223 | 0.105 | 35 | 0.077 |
| 1 | 2023-03-30..2024-03-13 | 2024-03-14..2024-06-10 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 199 | 0.125 | 42 | 0.099 |
| 2 | 2023-06-27..2024-06-10 | 2024-06-11..2024-09-05 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 178 | 0.121 | 54 | 0.148 |
| 3 | 2023-09-22..2024-09-05 | 2024-09-06..2024-12-03 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 175 | 0.112 | 47 | 0.054 |
| 4 | 2023-12-20..2024-12-03 | 2024-12-04..2025-02-28 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 179 | 0.108 | 42 | 0.137 |
| 5 | 2024-03-18..2025-02-28 | 2025-03-03..2025-05-28 | {'signal_params.momentum_min_pct': np.float64(0.1), 'exits.stop_loss_pct': np.float64(0.7)} | 184 | 0.111 | 55 | 0.061 |
| 6 | 2024-06-13..2025-05-28 | 2025-05-29..2025-08-25 | {'signal_params.momentum_min_pct': np.float64(0.1), 'exits.stop_loss_pct': np.float64(0.7)} | 197 | 0.108 | 44 | 0.014 |
| 7 | 2024-09-10..2025-08-25 | 2025-08-26..2025-11-20 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 186 | 0.068 | 52 | -0.020 |


### Parameter sensitivity (validation+test period)

| signal_params.momentum_min_pct | exits.stop_loss_pct | trades | exp_r | tstat | win_rate | profit_factor | net_pnl |
|---|---|---|---|---|---|---|---|
| 0.000 | 0.300 | 242 | 0.045 | 1.693 | 0.467 | 1.358 | 78,230.651 |
| 0.000 | 0.500 | 242 | 0.048 | 1.748 | 0.492 | 1.350 | 78,140.703 |
| 0.000 | 0.700 | 242 | 0.047 | 1.699 | 0.492 | 1.338 | 76,132.054 |
| 0.050 | 0.300 | 241 | 0.046 | 1.713 | 0.469 | 1.358 | 77,801.154 |
| 0.050 | 0.500 | 241 | 0.048 | 1.767 | 0.494 | 1.349 | 77,711.206 |
| 0.050 | 0.700 | 241 | 0.048 | 1.718 | 0.494 | 1.337 | 75,702.556 |
| 0.100 | 0.300 | 243 | 0.038 | 1.443 | 0.461 | 1.296 | 66,314.778 |
| 0.100 | 0.500 | 243 | 0.045 | 1.663 | 0.494 | 1.313 | 70,559.841 |
| 0.100 | 0.700 | 243 | 0.044 | 1.607 | 0.494 | 1.299 | 68,132.106 |
