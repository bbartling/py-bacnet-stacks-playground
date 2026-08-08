# Campaign audit — schedule → plant-proxy → hybrid v2

**Date (UTC):** 2026-08-08  
**Branch:** `feat/vibe22-eplus-schedule-plant-calib`  
**Freeze:** `0939584` / site `freeze_pre_schedule_plant_20260808T143015Z`  
**Champion parent:** `B_equip_mult_mid` (unchanged baseline)

## Verdict

**NO-GO** for DSM / paired farm / treatment promotion.

| Gate | Result |
| --- | --- |
| P1 schedule/calendar/OA structure | **PASS** — weekend/overnight left ~12.4 kW collapse |
| P2 nine→six zone temps | **SCREENING ONLY** — MAE ≈ 2.4–2.8 °F on repaired IdealLoads |
| P3 physical W2A plant | **PROVISIONAL PROXY** — IdealLoads plant-proxy knobs; W2A topology documented, not executable as-built |
| P4 multiobjective raw gates | evaluated on plant-proxy family (see summary JSON) |
| P5 `hybrid_dsm_96_v2` | contract published; training/farm **not** promoted |
| P6 paired DSM farm | **NOT RUN** (raw E+ ineligible) |

## Honest freeze

- IdealLoads + fixed-COP remains engineering / monthly screening only.
- Measured ML may continue for forecasting under existing contracts.
- **DSM NO-GO** — no prettier proxy, no fabricated treatment effects.
- `hybrid_dsm_96_v1` untouched; `hybrid_dsm_96_v2` is immutable sibling.

## Artifact pointers (site SoT)

- `eplus/campaigns/schedule_sanity_20260808T150000Z/`
- `eplus/campaigns/plant_proxy_calib_*/`
- `reports/eplus/zone_validation/`

Repo mirrors: `docs/superpowers/specs/2026-08-08-*-summary.json`, defect ledger, plant card.
