# Interval semantics audit — vibe_code_apps_22 (post interval15 fix)

**Date:** 2026-08-10  
**Canonical SoT:** [`ml/interval15.py`](../../ml/interval15.py) + [`contracts/hybrid_dsm_96_v1.json`](../../contracts/hybrid_dsm_96_v1.json)

## Contract (current)

| Field | Meaning |
|---|---|
| `q0` / `step_15=0` | `[00:00, 00:15)` stamped **00:15**, `hour_ending=0.25` |
| `q95` / `step_15=95` | `[23:45, 24:00)` stamped **24:00**, `hour_ending=24.0` |
| Init | Measured **00:00** midnight (lags only) |
| Weather | `weather[*][t]` never `t+1` |

## Physical-time × subsystem (POST-FIX)

Assumes Lakeside local-standard CST−6 for E+ stamps; REAL joins via America/Chicago civil then maps through `interval15`.

| Clock | REAL BAS | E+ farm | Python hybrid | Rust hybrid_onnx |
|---|---|---|---|---|
| **00:00** | site_date=prior day, q=95, HE=24.0; init only | stamp 00:00 → q=95 HE_int=24 | init JSON only | midnight init |
| **00:15** | q=0, HE=0.25, weather index 0 | q=0, HE_int=1 (not 24) | step0 HE=0.25, weather[0] | step0 HE=0.25 |
| **00:30** | q=1, HE=0.5 | q=1, HE_int=1 | step1 HE=0.5 | same |
| **01:00** | q=3, HE=1.0 | q=3, HE_int=1 | step3 HE=1.0 | same |
| **23:45** | q=94, HE=23.75 | q=94, HE_int=24 | step94 HE=23.75 | same |
| **24:00** | q=95 on that site_date | q=95, HE_int=24 | step95 HE=24.0 | same |

### Lag source at first prediction

| Subsystem | Lag source |
|---|---|
| REAL train | wall-time causal `.shift(1/2)` across midnight; compile **dropna** (never same-row `y[t]`) |
| E+ delta train | Δ shifts; pair-start → **0** to match serve |
| Python/Rust serve baseline | `init` midnight facility/zones/OAT |
| Python/Rust serve delta | facility/zone Δ lags **0**; oat_lag1 from init |

### Occupied / hours_to_occupy

Hybrid: occupied ≈ steps `[28,64)`; `hours_to_occupy = max(0,(28-step)/4)`.

## Pre-fix bugs (historical)

See archive/`legacy_quarter_index.py`, `legacy_hybrid_calendar.py`, `legacy_same_row_lag_fill.md`.
Farm mapped 00:15→HE24; hybrid used `hour_ending=step/4`; compile filled q0 lags from targets.

## Verification

- `tests/test_interval_golden_cross_subsystems.py`
- `tests/test_al_mission_gates.py` / `test_247_counterfactual_semantics.py`
- Rust `hour_ending_matches_interval15_contract`
- Wave 8 checklist in `simulation_root_cause_audit.md`
