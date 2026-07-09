# Stage 3/4 merge status report

**Date:** 2026-07-09  
**Branch merged:** `stage3-datafusion-parity-building100` → `master`  
**Latest commit:** see `git log -1` on master

## What works (proven @ 0.5h tolerance)

| area | status |
| --- | --- |
| Rust validate + ingest + Parquet cache | ✅ 48 equipment, ~1.5M rows, ~3s ingest |
| SQL rule batch | ✅ 19/19 rules execute |
| Zone analytics | ✅ AVG-ZONE-TEMP, ZONE-COMFORT-PCT, FAULT-ELAPSED-HOURS |
| VAV_7 zone_t role mapping | ✅ Fixed (ranked selection) |
| FC1, FC3, FC11, ECON-1 | ✅ Proven parity |
| FAN-RUNTIME-HOURS | ✅ Proven (where fan_cmd present) |
| SQL tuning API + static panel | ✅ `/api/sql-rules*`, `dashboard_sql_tuning.js` |
| Python oracle + dashboard | ✅ Unchanged; 103 pytest pass |

**Compare @ 0.5:** **314 pass / 54 fail / 11 skipped**

## What is NOT done / still failing

### AHU fault rules (material mismatch @ 0.5h — but only 1–8% hour deltas)

| rule | max Δh | notes |
| --- | ---: | --- |
| OAT-METEO | 32.7 | Weather timestamp alignment + confirm streak audit needed |
| FC8 | 29.8 | SAT/MAT economizer gate edge samples |
| ECON-4 | 26.0 | Confirm CTE added but streaks already saturated; fan/oa_frac audit |
| FC13 | 21.0 | sat_sp effective fallback vs raw SAT SP |
| FC10 | 20.3 | MAT-OAT sqrt tolerance |
| FC2 | 17.7 | Mixing envelope edge cases |
| FC9 | 17.6 | OAT vs SAT SP economizer |
| ECON-2 | 8.3 | Near parity |
| FC12 | 1.6 | Low hours — high % noise on AHU_2 |

### VAV-1 (34 equipment, all Δ < 7h)

Small confirm-window / comfort-band residuals per VAV box. Not material in absolute terms but fail strict 0.5h gate.

### Skipped (valid)

- **FC7 / ECON-5** — missing `htg_valve_pct`, `preheat_leave_t` on BUILDING_100 AHUs
- **FAN-RUNTIME** — plant equipment without `fan_cmd`
- **VAV_25A** — missing `zone_t`

## Not started

- React/TypeScript frontend rewrite
- Per-request Rust SQL preview with live param injection
- Full `parameters:` blocks for all 19 rules in registry
- Deleting pandas deterministic rule paths
- FC7/ECON-5 on BUILDING_100 without new historian columns

## Recommended next push

See [`STAGE4_PARITY_REMAINING_PLAN.md`](STAGE4_PARITY_REMAINING_PLAN.md):

1. OAT-METEO timestamp join audit (P0)
2. `debug_rule_parity.py` sample dumps for FC8/FC13 (P1)
3. Registry placeholders for FC8–FC10 thresholds (P2)
4. VAV-1 confirm alignment (P2)

## Do not delete yet

- `cookbook_engine.py` / `cookbook_rules.py` pandas paths
- `/api/cookbook/*` endpoints
- Legacy `dashboard_cookbook.js` sliders
