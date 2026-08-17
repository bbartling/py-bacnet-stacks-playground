# EnergyPlus multi-resolution calibration — Phase 0 baseline ledger

**Branch:** `feat/vibe22-multioutput-tutorial-notebooks` (PR #76)  
**Ledger commit (plan start):** `104cad6`  
**Site:** `LAKESIDE_SITE_ROOT` = `<SITE_ROOT>`  
**Captured:** 2026-08-07

## Staged twin (single champion)

| Field | Value |
| --- | --- |
| Staged IDF | `eplus/models/staged/lakeside_6zone_gshp_best_utility_dsm_v1.idf` |
| `DSM_ELIGIBLE.json` staged_sha256 | `169BF9FE007C7A3963ECDE31FDF07D7503DE77B3C91C6F02A468715829A4A7EB` |
| On-disk SHA256 | **matches** pointer (single champion — no disagreement) |
| Physics honesty | IdealLoads + fixed-COP electrical proxy (**not** GSHP/GLHE plant) |
| Filename note | `*gshp*` is historical naming only |

## Weather

| Field | Value |
| --- | --- |
| EPW | `eplus/weather/madison_amy_202508_202607.epw` |
| SHA256 | `dbfd1148a6627b53a1c6d5ba5e7b5fe7c4733fbe03865873d707d04ee22608d3` |

## Before metrics (immutable reference)

### Monthly utility GL14 (scorecard / DSM_ELIGIBLE)

| Metric | Value |
| --- | --- |
| Status | **pass** |
| NMBE % | 2.728 |
| CVRMSE % | 11.596 |
| n months | **11** (partial year — label honestly; not full 12) |

### Hourly measured-vs-modeled (`reports/eplus/mvm/mvm_summary.json`)

| Metric | Value |
| --- | --- |
| n_hourly | 8064 |
| hourly_nmbe_pct | ~3.11 |
| hourly_cvrmse_pct | **~97.27** |
| hourly_mae_kw | ~44.7 |
| Span UTC | 2025-08-01 → 2026-07-03 |

**Honesty gap:** monthly G14 passes while hourly CVRMSE is far above the 30% calibrated-sim screen.

### DSM farm (smoke)

| Field | Value |
| --- | --- |
| Usable both-arm pairs | **6** (&lt; 12) |
| Promote | requires `VIBE22_ALLOW_SMOKE_PROMOTE=1` |
| Label | screening-only / `smoke_artifact` — **not** operational DSM |

## Wave 0 code hygiene (this ledger commit)

- Ship selection: recursive held-out peak MAE only (no TF fallback)
- `ship_best_to_desktop` copies into `--artifacts`
- `--ship-desktop` requires both sklearn arms ok
- NaN-safe hybrid promote / rollout
- OOD fail-closed; chronological LOO (no future days); comfort violations computed on export
- Tests do not overwrite shipped nearest-day parity fixtures

## Out of scope until multi-res gates pass

- Mathematical control optimizer
- Claiming “15-minute GL14”
- Operational DSM recommendations on smoke farm
