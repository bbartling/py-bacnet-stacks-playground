# Campaign audit — schedule → plant → integrity closure

**Verdict: NO-GO** (DSM). Integrity-first closure supersedes the unreproducible W2A 20-run claim.

| Phase | Status |
| --- | --- |
| P0 | Defect ledger + characterization tests |
| P1 | 6/6 schedule sanity; **improvement-to-observed FAIL** (weekend overshoot 12.4→167 vs meas ~64 kW) |
| P2 | Nine→six MAE ~2.4–2.8°F; stratified + gallery |
| P3 | HVACTemplate W2A+loop smoke OK (not as-built GLHE) |
| P4a | IdealLoads plant-proxy 24/24; raw gates FAIL |
| P4b | Prior W2A calib **RETRACTED** (dead IdealLoads capacity knobs; W15–W19 non-reproducible) |
| P4c | **Integrity closure** `w2a_integrity_closure_20260808T161626Z`: 8 attempted / 8 unique / 8 succeeded; raw gates FAIL; hybrid-v2 farm **not run** |
| P4d | Creative push → **C02** monthly+weekend screen; monthly-held hourly dial `w2a_monthly_hold_hourly_dial_20260808T171328Z`: 8 attempts / 3 monthly passers; **no Feb hourly gain vs C02**; early stop; still NO-GO |
| P5 | `hybrid_dsm_96_v2` contract-only / unimplemented farm |
| P6 | Paired farm not run |

## Integrity closure counts

| Metric | Value |
| --- | --- |
| Attempted runs | 8 |
| Unique models (SHA256) | 8 |
| EnergyPlus succeeded | 8 |
| Raw gates any pass | false |
| Selection | Nov–Dec 2025 rolling origins (Jan holdout consumed) |
| Reserved final | Feb 2026 local month (not used for ranking) |
| Live knobs | post-ExpandObjects coil/fan/pump/OA/setpoint/optimum-start |

## Monthly-held hourly dial (C02 neighborhood)

| Metric | Value |
| --- | --- |
| Campaign | `w2a_monthly_hold_hourly_dial_20260808T171328Z` |
| Attempted | 8 (early stop; H08–H09 not needed) |
| Monthly GL14-style passers | 3 (`H00`, `H03`, `H07`) |
| Best by Feb hourly among passers | **H00_c02_ref** (same as C02; Feb CVRMSE ~36.8) |
| Beats C02 Feb by ≥1 pt | **false** |
| IdealLoads S0 | Historical monthly floor only — not this dial family |

## Honesty

- IdealLoads monthly engineering / screening only
- Provisional W2A is not as-built GSHP/GLHE
- Do not cite prior “W2A 20/20” or W15–W19
- DSM NO-GO — no residual/ML corrector to force raw E+ pass
- `hybrid_dsm_96_v1` not overwritten; v2 farm unimplemented
- Monthly hold is necessary for ranking, not sufficient for DSM / hourly