# Lag train/serve parity — hybrid DSM 96

**Date:** 2026-08-10  
**SoT serve:** [`ml/hybrid_rollout.py`](../../ml/hybrid_rollout.py)  
**SoT train (delta):** [`ml/train_eplus_delta_15min.py`](../../ml/train_eplus_delta_15min.py)

## Contract

Prediction at step `t` must **not** include target `y[t]` in lag features.  
Step 0 init = measured midnight state (baseline) or intervention zeros (delta).

## Feature sources at step 0 (serve)

| Feature | Baseline arm | Delta arm |
|---|---|---|
| `facility_kw_lag1` | `init.facility_kw` (midnight) | **0** (intervention start) |
| `facility_kw_lag2` | `init.facility_kw_lag2` or same as lag1 | **0** |
| `zone_temp_*_lag1` | `init.zone_temp_*` | **0** |
| `oat_lag1` | `init.oat_f` | `init.oat_f` (weather, not Δ) |
| `oat_f` / `rh_pct` / `ghi` | `weather_forecast_96[*][0]` | same |
| `step_15` / `hour_ending` | `interval15` → 0 / 0.25 | same |

## Training alignment

- Real baseline store: **causal wall-time** `.shift(1/2)` across midnight (not same-day-only);
  `matrix_xy_15min_multi` **drops** rows still missing lags — never fills from `y[t]`.
- Delta training: causal shifts on **delta** targets; pair-start Δ lags **`fillna(0.0)`** to match serve intervention-state zeros.
- Archived bug note: [`archive/legacy_same_row_lag_fill.md`](../../archive/legacy_same_row_lag_fill.md).

## Verification tests

- `test_no_current_target_in_lag_features`
- `test_matrix_xy_never_fills_lag_from_current_target`
- `test_midnight_state_is_prior_state`
- `test_delta_serve_lags_start_at_zero`
- `test_feature_lag_same_row_fillna_removed`
