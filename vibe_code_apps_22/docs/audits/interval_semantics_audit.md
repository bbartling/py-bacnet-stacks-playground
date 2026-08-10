# Interval semantics audit — vibe_code_apps_22

**Date:** 2026-08-10  
**Scope:** Prove 15-min timestamp / index / clock-feature semantics across REAL BAS, EnergyPlus farm, Python hybrid rollout, and Rust desktop.  
**Contract SoT:** [`contracts/hybrid_dsm_96_v1.json`](../../contracts/hybrid_dsm_96_v1.json)

## Canonical contract

| Field | Meaning |
|---|---|
| `q0` / `step_15=0` | Interval `[00:00, 00:15)`, prediction stamped **00:15**, `hour_ending=0.25` |
| `q95` / `step_15=95` | Interval `[23:45, 24:00)`, stamped **24:00**, `hour_ending=24.0` |
| Init | Measured **00:00** midnight state only (lags); not a prediction |
| Weather at step `t` | `weather_forecast_96[*][t]` — never `t+1` |

Implementation SoT after this rebuild: [`ml/interval15.py`](../../ml/interval15.py).

## Physical-time table (pre-fix evidence)

| Clock | REAL BAS (`build.py`) | E+ farm (`_quarter_index`) | Python hybrid | Rust `hybrid_onnx` |
|---|---|---|---|---|
| **00:00** | `step_15=0`, `hour_ending=0.0` | `he=24`, `q=95` (collides w/ 24:00) | init only | init only |
| **00:15** | `step_15=1`, `hour_ending=0.25` | `he=24` (**BUG**), `q=0` | doc 00:15; code `hour_ending=0.0` | same as Python |
| **00:30** | `step_15=2`, `hour_ending=0.5` | `he=24` (**BUG**), `q=1` | `hour_ending=0.25` | same |
| **01:00** | `step_15=4`, `hour_ending=1.0` | `he=1`, `q=3` | step4 → `1.0` | same |
| **23:45** | `step_15=95`, `hour_ending=23.75` | `he=23`, `q=94` | step95 → `23.75` | same |
| **24:00** | next-day 00:00 stamp | `he=24`, `q=95` | doc step95=24:00; code HE `23.75` | same |

### Citations (pre-fix)

- REAL: `ml/real_store/build.py` — `step_15 = hour*4 + minute//15`, `hour_ending = hour + (minute+14)//15*0.25`
- E+ farm: `scripts/eplus_heating_dsm_farm.py` — `_quarter_index` (legacy); `extract.interval_ending_local` disagreed
- Hybrid: `ml/hybrid_rollout.py` — `_calendar_features`: `hour_ending = step/4.0`
- Rust: `desktop/src/hybrid_onnx.rs` — `hour = step as f32 / 4.0`
- Tests: `tests/test_interval_semantics.py` protected weather[t] but not cross-subsystem step parity

## Weather / lag / demand notes

| Concern | REAL | E+ farm | Hybrid / Rust |
|---|---|---|---|
| Weather[t] | same-row join | hourly attach + **oat fill 25 / rh 50 / ghi 0** | `weather[t]`; rh/ghi defaults 50/0 |
| First-step lags | same-day shift → NaN → same-row fill | same-row fill | midnight init; delta lags 0 |
| Demand peak | N/A | N/A | Playground used **actual-day peak** as `existing_billing_peak` (invalid counterfactual) |

## Ranked findings

### CONFIRMED BUG
1. E+ farm mapped 00:15/00:30 → `hour_ending=24`.
2. E+ `00:00` and `24:00` both yielded `q=95`.
3. Farm `_quarter_index` ≠ `extract.interval_ending_local`.
4. Playground `existing_billing_peak_kw = nanmax(actual_day)`.

### HIGH-CONFIDENCE MODEL DEFECT
5. Contract `step0=00:15` vs REAL `00:15→step1` vs hybrid `hour_ending=step/4→0.0`.
6. Farm weather placeholders not EPW-native 15-min meteorology.
7. IdealLoads+COP DSM farm labeled as treatment while W2A champion is separate.

### PLAUSIBLE CONTRIBUTOR
8. Phase-shift between REAL and E+ clock features in hybrid sum.
9. One-day E+ RunPeriod warmup ≠ true thermal history.

### NOT SUPPORTED
10. REAL store hardcoding oat=25 / rh=50 / ghi=0.
11. EnergyPlus numerical divergence as primary cause of 97% hourly CVRMSE.
