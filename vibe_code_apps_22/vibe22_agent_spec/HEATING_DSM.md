# Vibe 22 — Heating DSM (Lakeside) — Hybrid Real+E+

**Last validated:** 2026-08-06 · Audit P0 honesty/desktop fixes · tip on `develop`.

## Product question

> For a chosen outdoor day, what is the **15-min × 96** facility kW and 6 area
> temps under **baseline** vs **DSM**, using
> `hybrid = real_baseline + eplus_delta`?

## Release posture

**Not operational DSM.** Product claim is **`HYBRID_SCREENING`** only:

- IdealLoads + fixed COP ≠ calibrated GSHP / electrical plant.
- Smoke paired farm (~6 both-arm pairs) is underpowered; strategy×weather confounded.
- Monthly GL14 energy pass ≠ 15-min peak / DSM transient validation.
- Promote refuses unless `cv_recursive_96_heldout` exists; pair count `< 12` needs `VIBE22_ALLOW_SMOKE_PROMOTE=1`.
- Desktop **Run** uses **live hybrid ONNX** from UI midnight state; ship JSON is compare/fallback, not the interactive engine.

## Architecture

```text
Real BAS 15-min store ──► real baseline 7-out (GB / ExtraTrees / RF + ResMLP)
                                    │
Paired E+ farm (6-area) ──► E+ delta 7-out     │
                                    │          │
                                    └────► hybrid 96-step rollout (Python + Rust live ONNX)
                                                 │
                                          desktop hybrid panel
```

**Locked rules**

- Keep sklearn (`gradient_boosting`, `extra_trees`, `random_forest`) and PyTorch ResMLP.
- Do **not** mix real BAS and EnergyPlus rows in one train table.
- Train + promote via notebooks only (`VIBE22_ALLOW_CLI_TRAIN=1` emergency).
- No cost optimizer yet — JSON contract is ready for a future optimizer.
- Never overwrite raw site inputs or canonical `*_best_utility.idf`.
- Honesty: **`HYBRID_SCREENING`** until field DSM trials + designed E+ farm + interval demand validation.

Prior kW-only stems live under `ml/artifacts/_quarantine_20260806/`.  
Defect list: [`NATIVE_EPLUS_DSM_REPORT.md`](NATIVE_EPLUS_DSM_REPORT.md).

## Ship champions (screening)

| Component | Family | Notes |
| --- | --- | --- |
| A — real baseline | **ExtraTrees** multi-output | Teacher-forced + **held-out recursive** on cards |
| B — E+ delta | bake-off champion | Smoke paired farm (expand with `--medium`) |
| C — hybrid walk | live ONNX + ship JSON | Desktop fail-closed without hybrid ONNX pair |
| Torch alt | ResMLP multi-head | Does **not** overwrite ship walk |

Lag init = **measured midnight** from JSON contract (never hardcoded 80 °F / 35 kW).

## Run order

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
$env:PYTHONUNBUFFERED="1"

# Data prep (CLI OK — not model training)
python -u scripts\build_real_15min_store.py
python -u scripts\eplus_heating_dsm_farm.py --smoke    # or --medium

# TRAIN + PROMOTE — notebooks only (Run All)
#   notebooks\lakeside_heating_dsm_sklearn.ipynb   # A + B + hybrid walk ship
#   notebooks\lakeside_heating_dsm_torch.ipynb     # ResMLP alt (does not overwrite ship)
# CLI ml\train_*.py and scripts\promote_hybrid_ship.py refuse unless VIBE22_ALLOW_CLI_TRAIN=1

python -u scripts\validate_mvm.py
cd desktop; cargo test hybrid_walk_loads --release
cargo run --release
```

## Ship surfaces

| Surface | Path |
| --- | --- |
| Real store | `scripts/build_real_15min_store.py` → site `ml/artifacts/real_baseline_15min_v1.parquet` |
| Real baseline | **sklearn notebook** → `real_baseline_15min_v1.*` (`ml/train_real_baseline_15min.py` helpers) |
| Paired farm | `scripts/eplus_heating_dsm_farm.py` → `heating_dsm_eplus_paired_15min_v1.parquet` |
| Delta model | **sklearn notebook** → `eplus_delta_15min_v1.*` |
| Hybrid rollout | `ml/hybrid_rollout.py` + `contracts/hybrid_dsm_96_v1.json` |
| Promote | **sklearn notebook** → `desktop/artifacts/hybrid_dsm_96_v1_walk.json` |
| MVM (hourly **and** 15-min) | `scripts/validate_mvm.py` |
| Desktop | `desktop/src/hybrid.rs` — baseline vs DSM trajectories |
| Human SoT notebook | `notebooks/lakeside_heating_dsm_sklearn.ipynb` (**only train path**) |
| Torch notebook | `notebooks/lakeside_heating_dsm_torch.ipynb` (**only ResMLP train path**) |

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
