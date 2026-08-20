# Vibe22 hp67 v1 physics repair failed (2026-08-19)

**Status:** `PHYSICS_REPAIR_FAILED_NOT_RL_ELIGIBLE`  
**RL eligible:** no  
**BACnet command authority:** 0

Child `a04_child_hp67_scaled_v1` ran real EnergyPlus on three development days. Per-zone capacity+airflow+water scaling from the 67-HP BAS inventory did **not** repair scored-runtime W2A low-airflow or frozen ramp gates.

## Independent audit summary

| Day | Peak kW | kWh | Max ramp (°F/15m) | W2A scored-runtime |
|-----|---------|-----|-------------------|-------------------|
| development_weekday (2026-01-12) | ~178.1 | ~1919 | ~13.03 | 1752 |
| development_weekend (2026-01-25) | ~104.4 | ~2109 | 36–46°F zones | 2022 |
| mild_weekday (2026-03-16) | ~191.6 | ~2311 | ~12.79 | 2263 |

Frozen ramp gate: **2.651 °F / 15 min** (not retuned).

## Evidence (compact scorecards only)

- Campaign: [`figures/a04_child_hp67_scaled_v1/campaign_summary.json`](figures/a04_child_hp67_scaled_v1/campaign_summary.json)
- Per day: `figures/a04_child_hp67_scaled_v1/<label>/compact_scorecard.json` + `slim_trajectory.json`
- Patch manifest: [`figures/a04_child_hp67_scaled_v1/patch_manifest.json`](figures/a04_child_hp67_scaled_v1/patch_manifest.json)

Raw `eplus_out/` trees are **not** committed (local render-only).

## v1 sizing flaw

Proportional water scaling used an invalid fallback (`water = air × 0.05`) when parent water flow was missing. v1 patch now **fail-closed** on that path. Follow-on work: **hp67 two-pass v2** (Autosize Pass 1 → EIO hard-size Pass 2).

## Honesty

- Not an operational DSM champion
- Not validated for long RL until physics repair passes gates
- `NO_PRISTINE_LOCKED_TEST_AVAILABLE`

Regenerate: `python scripts/a04_child_hp67_scaled_v1.py` (requires `$SITE_ROOT` + live EnergyPlus).
