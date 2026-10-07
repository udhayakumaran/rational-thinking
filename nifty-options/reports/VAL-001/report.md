# VAL-001 - Pipeline validation - EXP-001 design on SYNTHETIC NULL market

> **SYNTHETIC DATA - PIPELINE VALIDATION ONLY.** These numbers say nothing about the real NIFTY market and must not be compared with real-data experiments.

**Hypothesis.** Strong directional NIFTY moves (15-min opening-range breakout confirmed by VWAP and short-term momentum) may be expressed more efficiently through debit spreads than through naked long options.

**Data version:** `SYNTH-NULL-4548030d20`  |  **Walk-forward windows:** 8  |  **Runtime:** 360.3s

**Splits:** train 2023-01-02..2024-10-18, validation 2024-10-21..2025-05-27, test 2025-05-28..2025-12-31

## Variant comparison (identical signals, different option expression)

| variant | verdict | score | trades | OOS trades | OOS E[R] | OOS t | OOS PF | win% | avg win | avg loss | E[Rs]/lot | risk/lot | theta Rs/day | costs in R | theo E[R] | fits 1% budget | 1L port trades | 1L port maxDD | 1L share taken |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_long_atm | REJECT | 13.300 | 780 | 502 | -0.020 | -1.781 | 0.812 | 0.418 | 2,615.625 | 2,315.284 | -254.417 | 6,254.391 | -972.351 | 0.018 | -0.004 | 0.000 | 0 | -0.000 | 0.000 |
| B_atm_to_otm100 | REJECT | 21.000 | 780 | 502 | -0.068 | -4.202 | 0.620 | 0.404 | 695.702 | 771.689 | -179.089 | 2,429.724 | -86.084 | 0.076 | 0.006 | 0.005 | 4 | 0.017 | 0.005 |
| C_itm50_to_otm100 | REJECT | 11.700 | 780 | 502 | -0.042 | -2.865 | 0.722 | 0.417 | 1,068.995 | 1,031.944 | -156.553 | 3,906.568 | -64.027 | 0.050 | 0.011 | 0.000 | 0 | -0.000 | 0.000 |
| D_atm_wide300 | REJECT | 11.700 | 663 | 403 | -0.054 | -3.010 | 0.680 | 0.418 | 1,760.665 | 1,667.438 | -235.184 | 5,141.140 | -394.710 | 0.035 | -0.004 | 0.000 | 0 | -0.000 | 0.000 |


_E[R] = mean net P&L / planned max risk per trade (1 lot, realistic fills, all costs). 'theo E[R]' = mid-to-mid with no costs. 'fits 1% budget' = share of trades where one lot's max loss <= 1% of Rs 1L._


## Variant `A_long_atm`

`orb15:A_long_atm:long_opt[off+0]:SL0.7/EOD`  config `e0908ee56fc4`  chosen params: `{'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)}`

### Gate checks

| name | status | value | rule |
|---|---|---|---|
| sample_size_total | PASS | 780 | >= 150 |
| sample_size_oos | PASS | 502 | >= 60 |
| oos_expectancy_r | FAIL | -0.020 | >= 0.05 |
| oos_tstat | FLAG | -0.910 | >= 2.0 |
| oos_significance_multiple_testing | FAIL | {'p': 0.818, 'p_adj': 1.0, 'n_tests': 36} | Sidak-adjusted p <= 0.05 over all variants x grid points tried |
| oos_profit_factor | FAIL | 0.812 | >= 1.25 |
| oos_collapse | FAIL | -2.713 | OOS/IS >= 0.3 |
| profit_concentration_top10pct | N/A | - | total P&L not positive |
| best_year_share | N/A | - | total P&L not positive |
| estimated_spread_share | PASS | 0.000 | <= 0.2 (fills on unobserved quotes) |
| capital_feasibility | FLAG | 0.000 | >= 0.8 of trades fit 1 lot in the per-trade budget |
| regime_consistency | PASS | 2 | >= 2 regimes with >= 20 trades and E[R] > 0 |
| pessimistic_fill_expectancy | FAIL | -0.024 | > 0 under touch fills + slippage, on the same walk-forward OOS trades |
| edge_survives_costs | PASS | {'theoretical': -59179, 'net': -104231} | net > 0 whenever theoretical > 0 |
| parameter_plateau | FLAG | 0.000 | share of neighbours with positive val+test expectancy >= 0.6 |
| portfolio_tradable | FAIL | 0.000 | Rs 1L simulation with real limits takes >= 0.5 of research trades |


### Train / validation / test / walk-forward OOS

| period | trades | win_rate | expectancy | expectancy_r | expectancy_tstat | profit_factor | avg_winner | avg_loser | payoff_ratio | max_consec_losses |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 468 | 0.451 | -49.220 | 0.007 | -0.388 | 0.954 | 2,254.514 | 1,940.613 | 1.162 | 10 |
| validation | 157 | 0.408 | -307.298 | -0.020 | -1.015 | 0.802 | 3,049.768 | 2,617.538 | 1.165 | 10 |
| test | 155 | 0.329 | -820.414 | -0.109 | -2.585 | 0.588 | 3,564.829 | 2,970.870 | 1.200 | 7 |
| walk_forward_oos | 502 | 0.375 | -207.632 | -0.020 | -1.781 | 0.812 | 2,387.271 | 1,761.268 | 1.355 | 10 |


### Fill-model stress (test window)

| fill | trades | expectancy_r | profit_factor | total_pnl |
|---|---|---|---|---|
| optimistic | 155 | -0.104 | 0.605 | -120,390.651 |
| realistic | 155 | -0.109 | 0.588 | -127,164.222 |
| pessimistic | 155 | -0.113 | 0.576 | -132,181.399 |


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


Reference only - with divisible lots: median final 94,924, P(DD>=20%) 0.019.


_Monte Carlo assumes future trades resemble past ones; it measures luck, not model risk._


### By regime / volatility / direction / year


**by_regime**

| regime | trades | mean | win_rate | total |
|---|---|---|---|---|
| bear/high | 86 | -0.029 | 0.442 | -2.519 |
| bear/low | 90 | 0.021 | 0.467 | 1.889 |
| bear/normal | 86 | -0.028 | 0.419 | -2.388 |
| bear/unknown | 3 | -0.150 | 0.667 | -0.451 |
| bull/high | 48 | -0.105 | 0.312 | -5.062 |
| bull/low | 67 | 0.150 | 0.567 | 10.076 |
| bull/normal | 38 | -0.093 | 0.395 | -3.529 |
| range/high | 75 | -0.013 | 0.400 | -0.978 |
| range/low | 128 | -0.004 | 0.406 | -0.530 |
| range/normal | 102 | -0.096 | 0.353 | -9.803 |
| range/unknown | 7 | -0.194 | 0.286 | -1.359 |
| unknown/unknown | 50 | -0.041 | 0.400 | -2.026 |


**by_vol_regime**

| vol_regime | trades | mean | win_rate | total |
|---|---|---|---|---|
| high | 209 | -0.041 | 0.397 | -8.559 |
| low | 285 | 0.040 | 0.463 | 11.435 |
| normal | 226 | -0.070 | 0.385 | -15.719 |
| unknown | 60 | -0.064 | 0.400 | -3.836 |


**by_direction**

| direction | trades | mean | win_rate | total |
|---|---|---|---|---|
| BEARISH | 400 | 0.010 | 0.430 | 4.041 |
| BULLISH | 380 | -0.055 | 0.405 | -20.719 |


**by_year**

| year | trades | mean | win_rate | total |
|---|---|---|---|---|
| 2,023 | 259 | -0.014 | 0.456 | -3.577 |
| 2,024 | 261 | 0.010 | 0.429 | 2.525 |
| 2,025 | 260 | -0.060 | 0.369 | -15.626 |


**by_exit_reason**

| exit_reason | trades | mean | win_rate | total |
|---|---|---|---|---|
| eod_exit | 717 | 0.041 | 0.455 | 29.306 |
| stop_loss | 63 | -0.730 | 0.000 | -45.984 |


### Walk-forward windows

| k | train | test | params | is_trades | is_exp_r | oos_trades | oos_exp_r |
|---|---|---|---|---|---|---|---|
| 0 | 2023-01-02..2023-12-15 | 2023-12-18..2024-03-13 | {'signal_params.momentum_min_pct': np.float64(0.05), 'exits.stop_loss_pct': np.float64(0.3)} | 249 | 0.000 | 62 | 0.037 |
| 1 | 2023-03-30..2024-03-13 | 2024-03-14..2024-06-10 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.3)} | 248 | 0.031 | 63 | -0.016 |
| 2 | 2023-06-27..2024-06-10 | 2024-06-11..2024-09-05 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 248 | 0.032 | 63 | 0.024 |
| 3 | 2023-09-22..2024-09-05 | 2024-09-06..2024-12-03 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 249 | 0.026 | 63 | -0.057 |
| 4 | 2023-12-20..2024-12-03 | 2024-12-04..2025-02-28 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 249 | 0.014 | 63 | 0.004 |
| 5 | 2024-03-18..2025-02-28 | 2025-03-03..2025-05-28 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.3)} | 250 | -0.001 | 63 | 0.025 |
| 6 | 2024-06-13..2025-05-28 | 2025-05-29..2025-08-25 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.3)} | 250 | 0.010 | 63 | -0.066 |
| 7 | 2024-09-10..2025-08-25 | 2025-08-26..2025-11-20 | {'signal_params.momentum_min_pct': np.float64(0.05), 'exits.stop_loss_pct': np.float64(0.3)} | 250 | -0.012 | 62 | -0.109 |


### Parameter sensitivity (validation+test period)

| signal_params.momentum_min_pct | exits.stop_loss_pct | trades | exp_r | tstat | win_rate | profit_factor | net_pnl |
|---|---|---|---|---|---|---|---|
| 0.000 | 0.300 | 312 | -0.035 | -1.327 | 0.337 | 0.751 | -118,661.442 |
| 0.000 | 0.500 | 312 | -0.057 | -2.001 | 0.365 | 0.703 | -158,065.875 |
| 0.000 | 0.700 | 312 | -0.064 | -2.177 | 0.369 | 0.682 | -175,410.056 |
| 0.050 | 0.300 | 312 | -0.037 | -1.406 | 0.333 | 0.744 | -122,827.148 |
| 0.050 | 0.500 | 312 | -0.058 | -2.022 | 0.362 | 0.701 | -158,939.993 |
| 0.050 | 0.700 | 312 | -0.065 | -2.207 | 0.365 | 0.680 | -176,737.282 |
| 0.100 | 0.300 | 312 | -0.047 | -1.887 | 0.330 | 0.711 | -138,810.689 |
| 0.100 | 0.500 | 312 | -0.066 | -2.434 | 0.365 | 0.673 | -174,442.965 |
| 0.100 | 0.700 | 312 | -0.071 | -2.527 | 0.369 | 0.657 | -188,828.837 |


## Variant `B_atm_to_otm100`

`orb15:B_atm_to_otm100:debit_spread[off+0,w100]:SL0.7/EOD`  config `3e72d3c28926`  chosen params: `{'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)}`

### Gate checks

| name | status | value | rule |
|---|---|---|---|
| sample_size_total | PASS | 780 | >= 150 |
| sample_size_oos | PASS | 502 | >= 60 |
| oos_expectancy_r | FAIL | -0.068 | >= 0.05 |
| oos_tstat | FLAG | -4.250 | >= 2.0 |
| oos_significance_multiple_testing | FAIL | {'p': 1.0, 'p_adj': 1.0, 'n_tests': 36} | Sidak-adjusted p <= 0.05 over all variants x grid points tried |
| oos_profit_factor | FAIL | 0.620 | >= 1.25 |
| oos_collapse | FAIL | - | IS expectancy must be positive |
| profit_concentration_top10pct | N/A | - | total P&L not positive |
| best_year_share | N/A | - | total P&L not positive |
| estimated_spread_share | PASS | 0.000 | <= 0.2 (fills on unobserved quotes) |
| capital_feasibility | FLAG | 0.005 | >= 0.8 of trades fit 1 lot in the per-trade budget |
| regime_consistency | FLAG | 1 | >= 2 regimes with >= 20 trades and E[R] > 0 |
| pessimistic_fill_expectancy | FAIL | -0.083 | > 0 under touch fills + slippage, on the same walk-forward OOS trades |
| edge_survives_costs | PASS | {'theoretical': -1297, 'net': -84629} | net > 0 whenever theoretical > 0 |
| parameter_plateau | FLAG | 0.000 | share of neighbours with positive val+test expectancy >= 0.6 |
| portfolio_tradable | FAIL | 0.005 | Rs 1L simulation with real limits takes >= 0.5 of research trades |
| portfolio_max_drawdown | PASS | 0.017 | <= 0.15 |
| mc_p_drawdown_20pct | PASS | 0.000 | <= 0.1 |


### Train / validation / test / walk-forward OOS

| period | trades | win_rate | expectancy | expectancy_r | expectancy_tstat | profit_factor | avg_winner | avg_loser | payoff_ratio | max_consec_losses |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 468 | 0.421 | -110.757 | -0.056 | -3.221 | 0.687 | 576.589 | 610.414 | 0.945 | 12 |
| validation | 157 | 0.414 | -176.644 | -0.066 | -1.886 | 0.676 | 889.553 | 929.935 | 0.957 | 7 |
| test | 155 | 0.342 | -387.884 | -0.118 | -4.228 | 0.443 | 900.700 | 1,057.443 | 0.852 | 7 |
| walk_forward_oos | 502 | 0.382 | -168.583 | -0.068 | -4.202 | 0.620 | 720.019 | 718.943 | 1.001 | 8 |


### Fill-model stress (test window)

| fill | trades | expectancy_r | profit_factor | total_pnl |
|---|---|---|---|---|
| optimistic | 155 | -0.096 | 0.521 | -48,406.543 |
| realistic | 155 | -0.118 | 0.443 | -60,122.049 |
| pessimistic | 155 | -0.133 | 0.393 | -68,320.543 |


### Rs 1,00,000 portfolio simulation (risk limits enforced)

| trades | total_return | cagr | max_drawdown_pct | sharpe | sortino | calmar | max_dd_duration |
|---|---|---|---|---|---|---|---|
| 4 | -0.009 | -0.003 | 0.017 | -0.418 | -0.503 | -0.186 | 396 |


Rejections by stage: `{'risk': 776}`; top reasons: `{'one_lot_risk_#_exceeds_budget_#': 776}`


### Monte Carlo (block bootstrap of OOS trades, discrete lots at the configured risk %, 1-year horizon)

Share of resampled trades that fit at least one lot: 0.8%

| sims | trades/path | median final | p5 final | p95 maxDD | P(-10%) | P(-20%) | P(DD>=20%) | P(DD>=50%) | E[max losing streak] |
|---|---|---|---|---|---|---|---|---|---|
| 5,000 | 251 | 99,822.054 | 98,594.664 | 0.016 | 0.000 | 0.000 | 0.000 | 0.000 | 1.287 |


Reference only - with divisible lots: median final 83,997, P(DD>=20%) 0.254.


_Monte Carlo assumes future trades resemble past ones; it measures luck, not model risk._


### By regime / volatility / direction / year


**by_regime**

| regime | trades | mean | win_rate | total |
|---|---|---|---|---|
| bear/high | 86 | -0.070 | 0.395 | -6.047 |
| bear/low | 90 | -0.043 | 0.456 | -3.890 |
| bear/normal | 86 | -0.070 | 0.430 | -5.992 |
| bear/unknown | 3 | -0.111 | 0.667 | -0.333 |
| bull/high | 48 | -0.128 | 0.292 | -6.140 |
| bull/low | 67 | 0.070 | 0.582 | 4.662 |
| bull/normal | 38 | -0.123 | 0.421 | -4.667 |
| range/high | 75 | -0.080 | 0.360 | -6.019 |
| range/low | 128 | -0.061 | 0.398 | -7.821 |
| range/normal | 102 | -0.124 | 0.353 | -12.615 |
| range/unknown | 7 | -0.228 | 0.286 | -1.593 |
| unknown/unknown | 50 | -0.090 | 0.320 | -4.514 |


**by_vol_regime**

| vol_regime | trades | mean | win_rate | total |
|---|---|---|---|---|
| high | 209 | -0.087 | 0.359 | -18.206 |
| low | 285 | -0.025 | 0.460 | -7.049 |
| normal | 226 | -0.103 | 0.394 | -23.273 |
| unknown | 60 | -0.107 | 0.333 | -6.440 |


**by_direction**

| direction | trades | mean | win_rate | total |
|---|---|---|---|---|
| BEARISH | 400 | -0.050 | 0.415 | -20.200 |
| BULLISH | 380 | -0.091 | 0.392 | -34.768 |


**by_year**

| year | trades | mean | win_rate | total |
|---|---|---|---|---|
| 2,023 | 259 | -0.067 | 0.425 | -17.448 |
| 2,024 | 261 | -0.059 | 0.402 | -15.359 |
| 2,025 | 260 | -0.085 | 0.385 | -22.161 |


**by_exit_reason**

| exit_reason | trades | mean | win_rate | total |
|---|---|---|---|---|
| eod_exit | 739 | -0.033 | 0.426 | -24.412 |
| stop_loss | 41 | -0.745 | 0.000 | -30.555 |


### Walk-forward windows

| k | train | test | params | is_trades | is_exp_r | oos_trades | oos_exp_r |
|---|---|---|---|---|---|---|---|
| 0 | 2023-01-02..2023-12-15 | 2023-12-18..2024-03-13 | {'signal_params.momentum_min_pct': np.float64(0.05), 'exits.stop_loss_pct': np.float64(0.3)} | 249 | -0.063 | 62 | 0.016 |
| 1 | 2023-03-30..2024-03-13 | 2024-03-14..2024-06-10 | {'signal_params.momentum_min_pct': np.float64(0.05), 'exits.stop_loss_pct': np.float64(0.3)} | 248 | -0.028 | 63 | -0.079 |
| 2 | 2023-06-27..2024-06-10 | 2024-06-11..2024-09-05 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 248 | -0.033 | 63 | -0.061 |
| 3 | 2023-09-22..2024-09-05 | 2024-09-06..2024-12-03 | {'signal_params.momentum_min_pct': np.float64(0.05), 'exits.stop_loss_pct': np.float64(0.5)} | 249 | -0.040 | 63 | -0.127 |
| 4 | 2023-12-20..2024-12-03 | 2024-12-04..2025-02-28 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 249 | -0.058 | 63 | -0.034 |
| 5 | 2024-03-18..2025-02-28 | 2025-03-03..2025-05-28 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.5)} | 250 | -0.064 | 63 | -0.051 |
| 6 | 2024-06-13..2025-05-28 | 2025-05-29..2025-08-25 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.3)} | 250 | -0.060 | 63 | -0.080 |
| 7 | 2024-09-10..2025-08-25 | 2025-08-26..2025-11-20 | {'signal_params.momentum_min_pct': np.float64(0.05), 'exits.stop_loss_pct': np.float64(0.3)} | 250 | -0.065 | 62 | -0.131 |


### Parameter sensitivity (validation+test period)

| signal_params.momentum_min_pct | exits.stop_loss_pct | trades | exp_r | tstat | win_rate | profit_factor | net_pnl |
|---|---|---|---|---|---|---|---|
| 0.000 | 0.300 | 312 | -0.075 | -3.864 | 0.365 | 0.589 | -71,593.271 |
| 0.000 | 0.500 | 312 | -0.088 | -4.201 | 0.375 | 0.550 | -85,146.153 |
| 0.000 | 0.700 | 312 | -0.092 | -4.185 | 0.378 | 0.546 | -87,855.192 |
| 0.050 | 0.300 | 312 | -0.076 | -3.931 | 0.362 | 0.584 | -72,823.553 |
| 0.050 | 0.500 | 312 | -0.088 | -4.220 | 0.372 | 0.548 | -85,331.116 |
| 0.050 | 0.700 | 312 | -0.092 | -4.208 | 0.375 | 0.544 | -88,107.517 |
| 0.100 | 0.300 | 312 | -0.079 | -4.254 | 0.362 | 0.567 | -74,975.115 |
| 0.100 | 0.500 | 312 | -0.092 | -4.528 | 0.375 | 0.531 | -88,568.215 |
| 0.100 | 0.700 | 312 | -0.093 | -4.428 | 0.378 | 0.531 | -89,863.716 |


## Variant `C_itm50_to_otm100`

`orb15:C_itm50_to_otm100:debit_spread[off-1,w150]:SL0.3/EOD`  config `91880cf516c1`  chosen params: `{'signal_params.momentum_min_pct': np.float64(0.05), 'exits.stop_loss_pct': np.float64(0.3)}`

### Gate checks

| name | status | value | rule |
|---|---|---|---|
| sample_size_total | PASS | 780 | >= 150 |
| sample_size_oos | PASS | 502 | >= 60 |
| oos_expectancy_r | FAIL | -0.042 | >= 0.05 |
| oos_tstat | FLAG | -2.860 | >= 2.0 |
| oos_significance_multiple_testing | FAIL | {'p': 0.9979, 'p_adj': 1.0, 'n_tests': 36} | Sidak-adjusted p <= 0.05 over all variants x grid points tried |
| oos_profit_factor | FAIL | 0.722 | >= 1.25 |
| oos_collapse | FAIL | - | IS expectancy must be positive |
| profit_concentration_top10pct | N/A | - | total P&L not positive |
| best_year_share | N/A | - | total P&L not positive |
| estimated_spread_share | PASS | 0.000 | <= 0.2 (fills on unobserved quotes) |
| capital_feasibility | FLAG | 0.000 | >= 0.8 of trades fit 1 lot in the per-trade budget |
| regime_consistency | FLAG | 1 | >= 2 regimes with >= 20 trades and E[R] > 0 |
| pessimistic_fill_expectancy | FAIL | -0.053 | > 0 under touch fills + slippage, on the same walk-forward OOS trades |
| edge_survives_costs | FAIL | {'theoretical': 279, 'net': -87788} | net > 0 whenever theoretical > 0 |
| parameter_plateau | FLAG | 0.000 | share of neighbours with positive val+test expectancy >= 0.6 |
| portfolio_tradable | FAIL | 0.000 | Rs 1L simulation with real limits takes >= 0.5 of research trades |


### Train / validation / test / walk-forward OOS

| period | trades | win_rate | expectancy | expectancy_r | expectancy_tstat | profit_factor | avg_winner | avg_loser | payoff_ratio | max_consec_losses |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 468 | 0.442 | -81.494 | -0.027 | -1.702 | 0.827 | 878.664 | 842.998 | 1.042 | 8 |
| validation | 157 | 0.408 | -115.752 | -0.034 | -0.918 | 0.833 | 1,421.255 | 1,173.477 | 1.211 | 7 |
| test | 155 | 0.348 | -424.509 | -0.080 | -3.419 | 0.531 | 1,381.107 | 1,389.888 | 0.994 | 7 |
| walk_forward_oos | 502 | 0.414 | -174.876 | -0.042 | -2.865 | 0.722 | 1,095.702 | 1,073.789 | 1.020 | 7 |


### Fill-model stress (test window)

| fill | trades | expectancy_r | profit_factor | total_pnl |
|---|---|---|---|---|
| optimistic | 155 | -0.065 | 0.604 | -52,629.182 |
| realistic | 155 | -0.080 | 0.531 | -65,798.940 |
| pessimistic | 155 | -0.091 | 0.483 | -75,470.993 |


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


Reference only - with divisible lots: median final 89,760, P(DD>=20%) 0.021.


_Monte Carlo assumes future trades resemble past ones; it measures luck, not model risk._


### By regime / volatility / direction / year


**by_regime**

| regime | trades | mean | win_rate | total |
|---|---|---|---|---|
| bear/high | 86 | -0.036 | 0.477 | -3.110 |
| bear/low | 90 | -0.013 | 0.456 | -1.169 |
| bear/normal | 86 | -0.038 | 0.430 | -3.234 |
| bear/unknown | 3 | -0.378 | 0.000 | -1.135 |
| bull/high | 48 | -0.082 | 0.312 | -3.945 |
| bull/low | 67 | 0.074 | 0.582 | 4.985 |
| bull/normal | 38 | -0.075 | 0.421 | -2.868 |
| range/high | 75 | -0.038 | 0.373 | -2.875 |
| range/low | 128 | -0.035 | 0.406 | -4.519 |
| range/normal | 102 | -0.088 | 0.343 | -8.970 |
| range/unknown | 7 | -0.153 | 0.286 | -1.069 |
| unknown/unknown | 50 | -0.047 | 0.380 | -2.362 |


**by_vol_regime**

| vol_regime | trades | mean | win_rate | total |
|---|---|---|---|---|
| high | 209 | -0.048 | 0.402 | -9.931 |
| low | 285 | -0.002 | 0.463 | -0.703 |
| normal | 226 | -0.067 | 0.389 | -15.073 |
| unknown | 60 | -0.076 | 0.350 | -4.566 |


**by_direction**

| direction | trades | mean | win_rate | total |
|---|---|---|---|---|
| BEARISH | 397 | -0.021 | 0.421 | -8.446 |
| BULLISH | 383 | -0.057 | 0.413 | -21.826 |


**by_year**

| year | trades | mean | win_rate | total |
|---|---|---|---|---|
| 2,023 | 259 | -0.036 | 0.436 | -9.211 |
| 2,024 | 261 | -0.032 | 0.425 | -8.306 |
| 2,025 | 260 | -0.049 | 0.388 | -12.755 |


**by_exit_reason**

| exit_reason | trades | mean | win_rate | total |
|---|---|---|---|---|
| eod_exit | 519 | 0.122 | 0.626 | 63.399 |
| stop_loss | 261 | -0.359 | 0.000 | -93.671 |


### Walk-forward windows

| k | train | test | params | is_trades | is_exp_r | oos_trades | oos_exp_r |
|---|---|---|---|---|---|---|---|
| 0 | 2023-01-02..2023-12-15 | 2023-12-18..2024-03-13 | {'signal_params.momentum_min_pct': np.float64(0.05), 'exits.stop_loss_pct': np.float64(0.3)} | 249 | -0.038 | 62 | 0.040 |
| 1 | 2023-03-30..2024-03-13 | 2024-03-14..2024-06-10 | {'signal_params.momentum_min_pct': np.float64(0.05), 'exits.stop_loss_pct': np.float64(0.3)} | 248 | -0.005 | 63 | -0.028 |
| 2 | 2023-06-27..2024-06-10 | 2024-06-11..2024-09-05 | {'signal_params.momentum_min_pct': np.float64(0.05), 'exits.stop_loss_pct': np.float64(0.3)} | 248 | -0.004 | 63 | -0.026 |
| 3 | 2023-09-22..2024-09-05 | 2024-09-06..2024-12-03 | {'signal_params.momentum_min_pct': np.float64(0.05), 'exits.stop_loss_pct': np.float64(0.3)} | 249 | -0.009 | 63 | -0.095 |
| 4 | 2023-12-20..2024-12-03 | 2024-12-04..2025-02-28 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.5)} | 249 | -0.027 | 63 | -0.011 |
| 5 | 2024-03-18..2025-02-28 | 2025-03-03..2025-05-28 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 250 | -0.037 | 63 | -0.045 |
| 6 | 2024-06-13..2025-05-28 | 2025-05-29..2025-08-25 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.3)} | 250 | -0.037 | 63 | -0.066 |
| 7 | 2024-09-10..2025-08-25 | 2025-08-26..2025-11-20 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.3)} | 250 | -0.046 | 62 | -0.106 |


### Parameter sensitivity (validation+test period)

| signal_params.momentum_min_pct | exits.stop_loss_pct | trades | exp_r | tstat | win_rate | profit_factor | net_pnl |
|---|---|---|---|---|---|---|---|
| 0.000 | 0.300 | 312 | -0.056 | -3.152 | 0.378 | 0.667 | -82,804.507 |
| 0.000 | 0.500 | 312 | -0.061 | -3.188 | 0.401 | 0.645 | -94,350.306 |
| 0.000 | 0.700 | 312 | -0.065 | -3.271 | 0.401 | 0.632 | -100,178.580 |
| 0.050 | 0.300 | 312 | -0.057 | -3.196 | 0.378 | 0.663 | -83,971.938 |
| 0.050 | 0.500 | 312 | -0.062 | -3.224 | 0.401 | 0.642 | -95,315.921 |
| 0.050 | 0.700 | 312 | -0.065 | -3.293 | 0.401 | 0.630 | -100,537.902 |
| 0.100 | 0.300 | 312 | -0.060 | -3.482 | 0.381 | 0.644 | -88,791.588 |
| 0.100 | 0.500 | 312 | -0.064 | -3.404 | 0.401 | 0.628 | -98,647.757 |
| 0.100 | 0.700 | 312 | -0.068 | -3.530 | 0.401 | 0.609 | -106,803.123 |


## Variant `D_atm_wide300`

`orb15:D_atm_wide300:debit_spread[off+0,w300]:SL0.5/EOD`  config `40500bca5fc1`  chosen params: `{'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.5)}`

### Gate checks

| name | status | value | rule |
|---|---|---|---|
| sample_size_total | PASS | 663 | >= 150 |
| sample_size_oos | PASS | 403 | >= 60 |
| oos_expectancy_r | FAIL | -0.054 | >= 0.05 |
| oos_tstat | FLAG | -2.750 | >= 2.0 |
| oos_significance_multiple_testing | FAIL | {'p': 0.997, 'p_adj': 1.0, 'n_tests': 36} | Sidak-adjusted p <= 0.05 over all variants x grid points tried |
| oos_profit_factor | FAIL | 0.680 | >= 1.25 |
| oos_collapse | FAIL | - | IS expectancy must be positive |
| profit_concentration_top10pct | N/A | - | total P&L not positive |
| best_year_share | N/A | - | total P&L not positive |
| estimated_spread_share | PASS | 0.000 | <= 0.2 (fills on unobserved quotes) |
| capital_feasibility | FLAG | 0.000 | >= 0.8 of trades fit 1 lot in the per-trade budget |
| regime_consistency | FLAG | 1 | >= 2 regimes with >= 20 trades and E[R] > 0 |
| pessimistic_fill_expectancy | FAIL | -0.060 | > 0 under touch fills + slippage, on the same walk-forward OOS trades |
| edge_survives_costs | PASS | {'theoretical': -60093, 'net': -123340} | net > 0 whenever theoretical > 0 |
| parameter_plateau | FLAG | 0.000 | share of neighbours with positive val+test expectancy >= 0.6 |
| portfolio_tradable | FAIL | 0.000 | Rs 1L simulation with real limits takes >= 0.5 of research trades |


### Train / validation / test / walk-forward OOS

| period | trades | win_rate | expectancy | expectancy_r | expectancy_tstat | profit_factor | avg_winner | avg_loser | payoff_ratio | max_consec_losses |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 407 | 0.447 | -105.291 | -0.020 | -1.196 | 0.862 | 1,472.672 | 1,381.688 | 1.066 | 10 |
| validation | 124 | 0.419 | -227.803 | -0.039 | -0.967 | 0.799 | 2,157.587 | 1,950.584 | 1.106 | 10 |
| test | 132 | 0.326 | -642.619 | -0.096 | -2.791 | 0.559 | 2,499.612 | 2,160.775 | 1.157 | 7 |
| walk_forward_oos | 403 | 0.377 | -306.055 | -0.054 | -3.010 | 0.680 | 1,721.310 | 1,533.783 | 1.122 | 10 |


### Fill-model stress (test window)

| fill | trades | expectancy_r | profit_factor | total_pnl |
|---|---|---|---|---|
| optimistic | 132 | -0.087 | 0.594 | -76,005.392 |
| realistic | 132 | -0.096 | 0.559 | -84,825.668 |
| pessimistic | 132 | -0.102 | 0.536 | -90,747.857 |


### Rs 1,00,000 portfolio simulation (risk limits enforced)

| trades | total_return | cagr | max_drawdown_pct | sharpe | sortino | calmar | max_dd_duration |
|---|---|---|---|---|---|---|---|
| 0 | 0.000 | 0.000 | -0.000 | - | - | - | 0 |


Rejections by stage: `{'risk': 663, 'liquidity': 114, 'pricing': 3}`; top reasons: `{'one_lot_risk_#_exceeds_budget_#': 663, 'wide_spread:NIFTY#PE:#.#': 64, 'wide_spread:NIFTY#CE:#.#': 50, 'premium_below_min:NIFTY#PE:#.#': 40, 'premium_below_min:NIFTY#CE:#.#': 31}`


### Monte Carlo (block bootstrap of OOS trades, discrete lots at the configured risk %, 1-year horizon)

Share of resampled trades that fit at least one lot: 0.0%

| sims | trades/path | median final | p5 final | p95 maxDD | P(-10%) | P(-20%) | P(DD>=20%) | P(DD>=50%) | E[max losing streak] |
|---|---|---|---|---|---|---|---|---|---|
| 5,000 | 213 | 100,000.000 | 100,000.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |


Reference only - with divisible lots: median final 89,127, P(DD>=20%) 0.025.


_Monte Carlo assumes future trades resemble past ones; it measures luck, not model risk._


### By regime / volatility / direction / year


**by_regime**

| regime | trades | mean | win_rate | total |
|---|---|---|---|---|
| bear/high | 84 | -0.029 | 0.464 | -2.436 |
| bear/low | 71 | -0.014 | 0.451 | -0.974 |
| bear/normal | 71 | -0.052 | 0.394 | -3.698 |
| bear/unknown | 3 | -0.105 | 0.667 | -0.314 |
| bull/high | 47 | -0.091 | 0.319 | -4.271 |
| bull/low | 46 | 0.045 | 0.565 | 2.079 |
| bull/normal | 34 | -0.055 | 0.441 | -1.877 |
| range/high | 72 | -0.025 | 0.403 | -1.827 |
| range/low | 89 | -0.043 | 0.393 | -3.808 |
| range/normal | 89 | -0.067 | 0.382 | -5.989 |
| range/unknown | 7 | -0.178 | 0.286 | -1.244 |
| unknown/unknown | 50 | -0.024 | 0.400 | -1.200 |


**by_vol_regime**

| vol_regime | trades | mean | win_rate | total |
|---|---|---|---|---|
| high | 203 | -0.042 | 0.409 | -8.535 |
| low | 206 | -0.013 | 0.451 | -2.703 |
| normal | 194 | -0.060 | 0.397 | -11.564 |
| unknown | 60 | -0.046 | 0.400 | -2.757 |


**by_direction**

| direction | trades | mean | win_rate | total |
|---|---|---|---|---|
| BEARISH | 334 | -0.012 | 0.428 | -3.992 |
| BULLISH | 329 | -0.066 | 0.407 | -21.568 |


**by_year**

| year | trades | mean | win_rate | total |
|---|---|---|---|---|
| 2,023 | 238 | -0.033 | 0.454 | -7.814 |
| 2,024 | 204 | -0.017 | 0.431 | -3.385 |
| 2,025 | 221 | -0.065 | 0.367 | -14.360 |


**by_exit_reason**

| exit_reason | trades | mean | win_rate | total |
|---|---|---|---|---|
| eod_exit | 546 | 0.068 | 0.507 | 37.295 |
| stop_loss | 117 | -0.537 | 0.000 | -62.854 |


### Walk-forward windows

| k | train | test | params | is_trades | is_exp_r | oos_trades | oos_exp_r |
|---|---|---|---|---|---|---|---|
| 0 | 2023-01-02..2023-12-15 | 2023-12-18..2024-03-13 | {'signal_params.momentum_min_pct': np.float64(0.05), 'exits.stop_loss_pct': np.float64(0.3)} | 232 | -0.020 | 41 | -0.075 |
| 1 | 2023-03-30..2024-03-13 | 2024-03-14..2024-06-10 | {'signal_params.momentum_min_pct': np.float64(0.05), 'exits.stop_loss_pct': np.float64(0.3)} | 210 | -0.012 | 47 | -0.051 |
| 2 | 2023-06-27..2024-06-10 | 2024-06-11..2024-09-05 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.5)} | 194 | -0.010 | 58 | 0.028 |
| 3 | 2023-09-22..2024-09-05 | 2024-09-06..2024-12-03 | {'signal_params.momentum_min_pct': np.float64(0.1), 'exits.stop_loss_pct': np.float64(0.7)} | 192 | -0.007 | 51 | -0.090 |
| 4 | 2023-12-20..2024-12-03 | 2024-12-04..2025-02-28 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.7)} | 196 | -0.018 | 49 | 0.005 |
| 5 | 2024-03-18..2025-02-28 | 2025-03-03..2025-05-28 | {'signal_params.momentum_min_pct': np.float64(0.05), 'exits.stop_loss_pct': np.float64(0.7)} | 202 | -0.016 | 54 | -0.057 |
| 6 | 2024-06-13..2025-05-28 | 2025-05-29..2025-08-25 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.3)} | 209 | -0.019 | 50 | -0.096 |
| 7 | 2024-09-10..2025-08-25 | 2025-08-26..2025-11-20 | {'signal_params.momentum_min_pct': np.float64(0.0), 'exits.stop_loss_pct': np.float64(0.3)} | 201 | -0.052 | 53 | -0.110 |


### Parameter sensitivity (validation+test period)

| signal_params.momentum_min_pct | exits.stop_loss_pct | trades | exp_r | tstat | win_rate | profit_factor | net_pnl |
|---|---|---|---|---|---|---|---|
| 0.000 | 0.300 | 256 | -0.062 | -2.764 | 0.348 | 0.678 | -100,545.181 |
| 0.000 | 0.500 | 256 | -0.068 | -2.788 | 0.371 | 0.660 | -113,073.210 |
| 0.000 | 0.700 | 256 | -0.070 | -2.805 | 0.371 | 0.651 | -117,990.115 |
| 0.050 | 0.300 | 256 | -0.064 | -2.853 | 0.344 | 0.670 | -103,828.882 |
| 0.050 | 0.500 | 256 | -0.069 | -2.822 | 0.367 | 0.657 | -114,275.711 |
| 0.050 | 0.700 | 256 | -0.071 | -2.838 | 0.367 | 0.647 | -119,192.617 |
| 0.100 | 0.300 | 256 | -0.069 | -3.070 | 0.336 | 0.651 | -110,874.374 |
| 0.100 | 0.500 | 256 | -0.071 | -2.914 | 0.367 | 0.640 | -121,095.276 |
| 0.100 | 0.700 | 256 | -0.073 | -2.931 | 0.367 | 0.630 | -126,139.459 |
