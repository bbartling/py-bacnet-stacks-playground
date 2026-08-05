# Native EnergyPlus DSM — engineering report

**Date:** 2026-08-05  
**App:** `vibe_code_apps_22`  
**Site:** `LAKESIDE_SITE_ROOT=…/sp_creekside`

## What changed

Production heating DSM labels now come only from **validated native EnergyPlus runs** of a **staged** repair of the utility champion (`util_103` lineage). The old BAS `physics_proxy_kw` path stamped `ENERGYPLUS_SIMULATED` is **disabled** in production (`train_parquet_path` fails closed unless `LAKESIDE_DEMO_NOT_ENERGYPLUS=1`).

## Champion verification (Phase 0)

| Asset | SHA-256 | Match |
| --- | --- | --- |
| `lakeside_6zone_gshp_best_utility.idf` | `23EBE520…5EA83B` | yes |
| `madison_amy_202508_202607.epw` | `DBFD1148…22608D3` | yes |

Existing `util_103` completed with **14 Severe / 0 Fatal** — not DSM-eligible.

## Repair (Phase 1)

Staged IDF: `eplus/models/staged/lakeside_6zone_gshp_best_utility_dsm_v1.idf`  
SHA-256: `169BF9FE007C7A3963ECDE31FDF07D7503DE77B3C91C6F02A468715829A4A7EB`

Changes:

- `SCH_HtgSP` / `SCH_ClgSP`: DesignDay + AllOtherDays (fixes 0°C sizing SP)
- Building max warmup days 25 → 50
- Timestep meters/variables for DSM extraction
- Schedule `Until:14:40` → `14:45`

**Native full-year re-run:** 0 Fatal, **0 Severe**, accepted.  
**Monthly utility GL14 after repair:** NMBE **2.728%**, CVRMSE **11.596%**, status **pass** (still inside gates; NMBE moved from −0.079%).

Canonical champion files were **not** overwritten in place.

## Farm

- Smoke: 12/12 accepted  
- Medium: **162–165** accepted scenario-days, provenance `ENERGYPLUS_NATIVE_RUN`  
- Design-day rows filtered from training parquet (24 h/scenario)

## Measured vs modeled

Artifacts: `reports/eplus/mvm/` (+ desktop copy).

Interval demand (IdealLoads+COP vs 5-min→hourly measured):

- MAE ≈ **45 kW**, RMSE ≈ **64 kW**, NMBE ≈ **3.1%**  
- CVRMSE remains high vs interval demand — **monthly GL14 pass ≠ hourly peak fidelity**

Monthly utility GL14 is reported **separately** in the summary and desktop panel.

## Honesty / limits

- Electric demand = **Ideal Loads + fixed-COP proxy** (COP 3.5 / 4.5), not GSHP/GLHE plant
- Desktop peak MAE band is a **screening metric**, not an uncertainty interval
- Farm strategies patch heating setpoint schedules only
- Human SoT notebook: `notebooks/lakeside_heating_dsm_sklearn.ipynb` (scoreboard section)

## CI

`.github/workflows/vibe22-ci.yml` — pytest (`tests/test_eplus_native.py`) + `cargo test` on desktop.
