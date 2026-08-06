# Vibe 22 — Heating DSM (Lakeside) — Hybrid Real+E+

**Last validated:** 2026-08-06 · tip `040ae18` on `develop` · vibe22-ci green.

## Product question

> For a chosen outdoor day, what is the **15-min × 96** facility kW and 6 area
> temps under **baseline** vs **DSM**, using
> `hybrid = real_baseline + eplus_delta`?

## Architecture

```text
Real BAS 15-min store ──► real baseline 7-out (GB / ExtraTrees / RF + ResMLP)
                                    │
Paired E+ farm (6-area) ──► E+ delta 7-out     │
                                    │          │
                                    └────► hybrid 96-step rollout
                                                 │
                                          desktop hybrid panel
```

**Locked rules**

- Keep sklearn (`gradient_boosting`, `extra_trees`, `random_forest`) and PyTorch ResMLP.
- Do **not** mix real BAS and EnergyPlus rows in one train table.
- No cost optimizer yet — JSON contract is ready for a future optimizer.
- Never overwrite raw site inputs or canonical `*_best_utility.idf`.
- Honesty: **`HYBRID_SCREENING`** until field DSM trials.

Prior kW-only stems live under `ml/artifacts/_quarantine_20260806/`.  
Defect list: [`NATIVE_EPLUS_DSM_REPORT.md`](NATIVE_EPLUS_DSM_REPORT.md).

## Ship champions (screening)

| Component | Family | Notes |
| --- | --- | --- |
| A — real baseline | **ExtraTrees** multi-output | ~10.4 kW peak MAE (teacher-forced, winter subsample) |
| B — E+ delta | **RandomForest** multi-output | Smoke paired farm (expand with `--medium`) |
| C — hybrid walk | `hybrid_dsm_96_v1_walk.json` | Desktop fail-closed without this file |
| Torch alt | ResMLP multi-head | Does **not** overwrite ship walk |

Lag init = **measured midnight** from JSON contract (never hardcoded 80 °F / 35 kW).

## Run order

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
$env:PYTHONUNBUFFERED="1"

# A) Real 15-min store + baseline
python -u scripts\build_real_15min_store.py
python -u ml\train_real_baseline_15min.py --winter-only
python -u ml\train_real_baseline_torch_15min.py --winter-only   # optional alt

# B) Paired E+ farm + delta
python -u scripts\eplus_heating_dsm_farm.py --smoke    # or --medium
python -u ml\train_eplus_delta_15min.py

# C) Hybrid promote + MVM + desktop
python -u scripts\promote_hybrid_ship.py
python -u scripts\validate_mvm.py
cd desktop; cargo test hybrid_walk_loads --release
cargo run --release
```

## Ship surfaces

| Surface | Path |
| --- | --- |
| Real store | `scripts/build_real_15min_store.py` → site `ml/artifacts/real_baseline_15min_v1.parquet` |
| Real baseline | `ml/train_real_baseline_15min.py` → `real_baseline_15min_v1.*` |
| Paired farm | `scripts/eplus_heating_dsm_farm.py` → `heating_dsm_eplus_paired_15min_v1.parquet` |
| Delta model | `ml/train_eplus_delta_15min.py` → `eplus_delta_15min_v1.*` |
| Hybrid rollout | `ml/hybrid_rollout.py` + `contracts/hybrid_dsm_96_v1.json` |
| Promote | `scripts/promote_hybrid_ship.py` → `desktop/artifacts/hybrid_dsm_96_v1_walk.json` |
| MVM (hourly **and** 15-min) | `scripts/validate_mvm.py` |
| Desktop | `desktop/src/hybrid.rs` — baseline vs DSM trajectories |
| Human SoT notebook | `notebooks/lakeside_heating_dsm_sklearn.ipynb` |
| Torch notebook | `notebooks/lakeside_heating_dsm_torch.ipynb` |

## Peak / metrics honesty

- Morning heating startup: local HE **05–09** → 15-min steps **20–36**.
- Always publish **teacher-forced** and **recursive 96-step** metrics on cards.
- Also report 15-min max demand error (MVM).
- E+ LST → UTC uses **fixed CST−6** (no Chicago DST on E+ stamps).
- IdealLoads + COP (3.5 heat / 4.5 cool) remains the E+ electric honesty label.

## Out of scope (this rebuild)

- Cost / tariff optimizer loop
- Live BACnet
- Treating hybrid as tariff-grade without field DSM trials
