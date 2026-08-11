# Simulation root-cause audit — vibe_code_apps_22

**Date:** 2026-08-10 (A–L + Wave 8 contract audit gate)  
**SoT:** [`contracts/hybrid_dsm_96_v1.json`](../../contracts/hybrid_dsm_96_v1.json)

## Bottom line

Interfaces (clock, weather provenance, thermal history, IdealLoads-as-treatment, billing)
dominate over “bigger nets.” Wave 8 blocking audit: **PASS** on the 10-gate checklist
(local pytest + cargo). Do **not** promote solely because smoke retrain scores moved.

## Ranked findings

| Rank | Finding | File / function | Evidence | Consequence | Smallest test | Fix | Verification |
|---|---|---|---|---|---|---|---|
| CONFIRMED | E+ farm HE=24 for 00:15/00:30 | `archive/legacy_quarter_index.py` | formula returned he=h for mi>0 with h=0→24 | weather join / occupied wrong | `test_eplus_0015_not_he24` | `interval15.from_eplus_stamp` | golden cross-subsystem |
| CONFIRMED | Hybrid HE=step/4 | `archive/legacy_hybrid_calendar.py` | step0→0.0 | clock features shifted | hour_ending≈0.25 | `calendar_features_for_step` | feature_parity golden 5.25@step20 |
| CONFIRMED | Silent oat=25/rh=50/ghi=0 | farm fillna (historical) | placeholders | false weather | `test_no_promotable_weather_fallback_gate` | fail-closed + eplus export | farm gate |
| CONFIRMED | Billing used actual-day peak | playground gen (historical) | nanmax(actual) | no demand credit | `test_month_peak_counterfactual` | `mtd_peak_before_day` | `test_billing_counterfactual_240_dollar_golden` |
| CONFIRMED | q0 lag = same-row target | `feature_compile_15min` / heating_dsm (historical) | `fillna(TARGET_COL)` | train/serve leakage | `test_matrix_xy_never_fills_lag_from_current_target` | dropna + cross-midnight shift; Δ fillna(0) | lag_train_serve_parity |
| HIGH | IdealLoads ≠ W2A treatment | farm PHYSICS_* | IdealLoads+COP | bad ΔP | `test_physics_family_labels` | STRUCTURAL vs W2A + scaffold | scaffold meta |
| HIGH | One-day history | `patch_run_period` | warmup ≠ prior days | unfair 24/7 | pre-roll harness | `--pre-roll-days` | spinup CSV |
| HIGH | Non-identifiable A04 knobs | W2A dial docs | multi-knob fit | non-unique physics | N/A | grey-box manifest | `greybox_sensor_manifest` |
| HIGH | Playground RH=55 default | `_gen_desktop…` / gallery | `np.full(96, 55)` when col missing | diagnostic weather | viewer only | label ILLUSTRATIVE / require column | honesty notes |
| PLAUSIBLE | Smoke strategy×weather confound | HEATING_DSM | one strat/day | confounded learner | pair integrity | require `--crossed` | docs + integrity |
| NOT_SUPPORTED | E+ solver divergence as main CVRMSE | farm rejects severe | — | — | — | — | — |
| NOT_SUPPORTED | Hourly IdealLoads GL14 miss caused by q-hour clock | prior multi-res | whole-hour lag=0 | — | — | keep as structural plant limit | prior audit |

## Wave 8 PASS checklist

1. [x] Cross-subsystem interval goldens  
2. [x] No-current-target lag  
3. [x] Midnight-state  
4. [x] E+ weather identity / fail-closed  
5. [x] Pre-roll harness / extraction path (`--pre-roll-days` + spinup CSV)  
6. [x] Timestep sensitivity harness 4/6/12  
7. [x] IdealLoads honesty gate  
8. [x] Prior-MTD billing ($240 golden)  
9. [x] Python/Rust feature parity (`test_feature_parity` / `test_parity_e2e` / Rust HE contract)  
10. [ ] `vibe22-ci` green on PR + develop (Wave 6)

## Invalidation map

| Defect class | Invalidates |
|---|---|
| Clock / HE | ML training features, runtime inference |
| q0 lag leak | ML training, train≠serve |
| Weather silent fill | Treatment attribution, training |
| Billing actual-day peak | Billing counterfactual economics |
| IdealLoads-as-W2A claim | Treatment validity (not just fit) |

## Safe for screening

Clock-aligned hybrid + fail-closed weather + IdealLoads as **STRUCTURAL_LOAD_DIAGNOSTIC** only.
Smoke retrain after contract fix is **HYBRID_SCREENING** — not operational DSM.

## Unsafe for operational DSM

IdealLoads treatment as plant truth; smoke farm; missing plant sensors; unverified tariff;
no measured ΔP on W2A; no BACnet writes.

## Deliverables

- [x] interval_semantics_audit.md / simulation_root_cause_audit.md / lag_train_serve_parity.md  
- [x] spinup_sensitivity.csv / timestep_sensitivity.csv / treatment_validation.csv  
- [x] greybox_sensor_manifest.md/.csv + GREYBOX_SHADOW_V1 design doc  
- [x] archive/ superseded helpers (incl. same-row lag fill note)  
- [x] smoke `train_four_arms` after contract fix (no promote)  
