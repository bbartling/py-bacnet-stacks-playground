# Vibe 22 — Heating DSM (Lakeside) — Hybrid Real+E+

## Product question

> For a chosen outdoor day, what is the **15-min × 96** facility kW and 6 area
> temps under **baseline** vs **DSM**, using `hybrid = real_baseline + eplus_delta`?

## Architecture

```text
Real BAS 15-min store ──► real baseline 7-out (GB/ET/RF + ResMLP)
                                    │
Paired E+ farm (6-area) ──► E+ delta 7-out     │
                                    │          │
                                    └────► hybrid 96-step rollout
                                                 │
                                          desktop hybrid panel
```

**Do not** mix real BAS and EnergyPlus rows in one train table.  
Honesty: **HYBRID_SCREENING**. IdealLoads+COP ≠ GSHP.

Prior kW-only stems quarantined under `ml/artifacts/_quarantine_*`.  
See [`NATIVE_EPLUS_DSM_REPORT.md`](NATIVE_EPLUS_DSM_REPORT.md) (superseded defects).

## Ship surfaces

| Surface | Path |
| --- | --- |
| Real store | `scripts/build_real_15min_store.py` → site `ml/artifacts/real_baseline_15min_v1.parquet` |
| Real baseline | `ml/train_real_baseline_15min.py` → `real_baseline_15min_v1.*` |
| Paired farm | `scripts/eplus_heating_dsm_farm.py` → `heating_dsm_eplus_paired_15min_v1.parquet` |
| Delta model | `ml/train_eplus_delta_15min.py` → `eplus_delta_15min_v1.*` |
| Hybrid rollout | `ml/hybrid_rollout.py` + `contracts/hybrid_dsm_96_v1.json` |
| Promote | `scripts/promote_hybrid_ship.py` → `desktop/artifacts/hybrid_dsm_96_v1_walk.json` |
| MVM (15-min) | `scripts/validate_mvm.py` |
| Desktop | `desktop/` hybrid panel (fail-closed without walk JSON) |

## Peak window

Morning heating startup HE 05–09 local (steps 20–36 at 15-min). Also report 15-min max demand error.

## Lag init

Measured midnight state from JSON contract — never hardcoded 80 °F / 35 kW.
