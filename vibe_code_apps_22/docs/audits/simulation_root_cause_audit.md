# Simulation root-cause audit — vibe_code_apps_22

**Date:** 2026-08-10  
**Mission:** Rank why hybrid DSM simulation “sucks” and what this rebuild fixes vs defers.

## Bottom line

Interfaces (clock, weather provenance, thermal history, IdealLoads-as-treatment, billing counterfactual) dominate. Do **not** respond with more IdealLoads knobs or a larger unconstrained network first.

Recommended order (this PR implements the front of the chain):

`clock/data contract → thermal-history scaffold → W2A honesty labels → treatment gates → cost counterfactual`

## Ranked findings

| Rank | Finding | Evidence | Consequence | Fix in this PR |
|---|---|---|---|---|
| CONFIRMED BUG | 15-min index/clock mismatch across REAL / E+ / hybrid / Rust | [`interval_semantics_audit.md`](interval_semantics_audit.md) | Recursive hybrid adds misaligned clock states | `interval15.py` + wire all four |
| CONFIRMED BUG | E+ farm HE=24 for 00:15/00:30 | `eplus_heating_dsm_farm._quarter_index` | Weather join + occupied features wrong near midnight | Use `interval15.from_eplus_stamp` |
| CONFIRMED BUG | Silent oat=25 / rh=50 / ghi=0 on farm | farm row builder + `fillna(25)` | Delta learns fake weather response | Fail-closed on promotable; diagnostic flag only for placeholders |
| CONFIRMED BUG | Peak-day billing uses actual-day peak as pre-existing | playground generator | Suppresses demand-charge value of peak reduction | MTD peak **before** target day |
| HIGH-CONFIDENCE | IdealLoads+COP ≠ W2A plant treatment | farm physics strings; multi-res audits | Synthetic ΔP not real HP/loop physics | Label `STRUCTURAL_LOAD_DIAGNOSTIC`; scaffold `W2A_PHYSICAL_DSM` |
| HIGH-CONFIDENCE | One-day RunPeriod + warmup ≠ history | EnergyPlus warmup docs; farm `patch_run_period` same day | Preheat/setback/24-7 unfair | Configurable 3/7/14 pre-roll + sensitivity CSV |
| HIGH-CONFIDENCE | Non-identifiable A04 multi-knob fit | W2A dial docs | Aggregate fit ≠ unique physics | Deferred: sensor campaign / grey-box (not this PR) |
| PLAUSIBLE | Strategy×weather confounding on smoke farm | HEATING_DSM honesty | Learner confuses day with strategy | Honesty docs + crossed-mode requirement |
| PLAUSIBLE | Zone timestep 4/h sensitivity | E+ Timestep docs | Peak/cycling may shift | Timestep sensitivity scaffold |
| NOT SUPPORTED | E+ solver divergence as main CVRMSE driver | Farm rejects severe errors; structural IdealLoads audit | — | No change |

## What remains unsafe for operational DSM

- IdealLoads treatment deltas as plant truth
- Smoke farm (`UNDERPOWERED_SMOKE_FARM`) for strategy ranking
- Missing plant measurements (EWT/LWT, stages, pump, DOAS)
- Annual billing replay (still heuristic / future)
- Any BACnet write path

## What is now safer for screening

- Cross-subsystem interval golden tests
- Fail-closed weather on promotable farm paths
- Majority E+-only scorecard (prior PR) + plant peak caps
- Incremental demand with correct pre-day billing peak in playground

## Deliverables checklist

- [x] `docs/audits/interval_semantics_audit.md`
- [x] `docs/audits/simulation_root_cause_audit.md`
- [x] `reports/eplus/spinup_sensitivity.csv` (scaffold)
- [x] `reports/eplus/timestep_sensitivity.csv` (scaffold)
- [x] `reports/ml/treatment_validation.csv` (scaffold / synthetic)
- [x] Golden tests + weather/treatment gates in CI
- [x] Superseded helpers archived under `archive/`
- [x] AGENTS.md / HEATING_DSM.md / lakeside-heating-dsm skill updated
