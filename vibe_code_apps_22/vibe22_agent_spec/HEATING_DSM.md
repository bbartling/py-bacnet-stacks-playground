# Vibe 22 — Heating DSM (Lakeside) — Hybrid Real+E+

**Last validated:** 2026-08-07 · Parallel CLI train arms + ship-best-to-desktop · tip on `feat/vibe22-multioutput-tutorial-notebooks`.

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
- **Train outside Jupyter** via `scripts/train_four_arms.py` (notebooks are **results viewers** only).
- Ship desktop via `scripts/ship_best_to_desktop.py` (auto-picks best sklearn arm + promote + `cargo run`).
- No cost optimizer yet — JSON contract is ready for a future optimizer.
- Never overwrite raw site inputs or canonical `*_best_utility.idf`.
- Honesty: **`HYBRID_SCREENING`** until field DSM trials + designed E+ farm + interval demand validation.
- Torch never overwrites sklearn desktop hybrid stems.

Prior kW-only stems live under `ml/artifacts/_quarantine_20260806/`.  
Defect list: [`NATIVE_EPLUS_DSM_REPORT.md`](NATIVE_EPLUS_DSM_REPORT.md).  
Scripts map: [`../scripts/README.md`](../scripts/README.md).

## Ship champions (screening)

| Component | Family | Notes |
| --- | --- | --- |
| A — real baseline | bake-off winner per arm | Teacher-forced + **held-out recursive** on cards |
| B — E+ delta | bake-off champion | Smoke paired farm (expand with `--medium`) |
| C — hybrid walk | live ONNX + ship JSON | Desktop fail-closed without hybrid ONNX pair |
| Torch alt | ResMLP multi-head | Research under `ml/artifacts/runs/torch_*` only |

Lag init = **measured midnight** from JSON contract (never hardcoded 80 °F / 35 kW).

## Interval semantics (96 × 15-min)

- Timestamps are **quarter-hour interval end / hour-ending** (same as E+ CSV stamps).
- Contract `init` at **00:00** is **state only** (lags / midnight measured); not a prediction.
- Rollout predictions are **96 steps**: interval ends **00:15 … 24:00** (`step_15=0…95`).
- Weather features at step `t` use `weather_forecast_96[*][t]` — no future leak to `t+1`.
- Night HDD accumulator is **local** to the rollout call (never mutate `contract["_hdd_acc"]`).

## Run order

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
$env:PYTHONUNBUFFERED="1"

# Data prep (CLI OK — not model training)
python -u scripts\build_real_15min_store.py
python -u scripts\eplus_heating_dsm_farm.py --smoke    # or --medium

# TRAIN — four arms in parallel (not Jupyter)
python -u scripts\train_four_arms.py --profile full_evaluation
# optional: --ship-desktop  (promote best sklearn + cargo run when arms OK)

# VIEW results (no training in-kernel)
#   notebooks\lakeside_heating_dsm_sklearn.ipynb
#   notebooks\lakeside_heating_dsm_torch.ipynb

# SHIP best sklearn baseline + existing delta → desktop, then launch sim
python -u scripts\ship_best_to_desktop.py
# promote-only: python -u scripts\ship_best_to_desktop.py --no-launch

python -u scripts\validate_mvm.py
```

If you need to **retrain the E+ delta** (component B), use legacy  
`scripts/run_sklearn_tutorial_train.py` (sets `VIBE22_ALLOW_CLI_TRAIN=1`) — four-arm matrix trains baselines only.

## Ship surfaces

| Surface | Path |
| --- | --- |
| Real store | `scripts/build_real_15min_store.py` → site `ml/artifacts/real_baseline_15min_v1.parquet` |
| Real baseline arms | `scripts/train_four_arms.py` → `ml/artifacts/runs/sklearn_{winter,allyear}/` |
| Torch arms | same launcher → `ml/artifacts/runs/torch_{winter,allyear}/` |
| Paired farm | `scripts/eplus_heating_dsm_farm.py` → `heating_dsm_eplus_paired_15min_v1.parquet` |
| Delta model | `ml/artifacts/eplus_delta_15min_v1.*` (retrain via `run_sklearn_tutorial_train.py` if needed) |
| Hybrid rollout | `ml/hybrid_rollout.py` + `contracts/hybrid_dsm_96_v1.json` |
| Promote + launch | `scripts/ship_best_to_desktop.py` → `desktop/artifacts/` + `cargo run --release` |
| MVM (hourly **and** 15-min) | `scripts/validate_mvm.py` |
| Desktop | `desktop/src/hybrid.rs` — baseline vs DSM trajectories |
| Sklearn viewer | `notebooks/lakeside_heating_dsm_sklearn.ipynb` |
| Torch viewer | `notebooks/lakeside_heating_dsm_torch.ipynb` |
| Load profile | `notebooks/lakeside_load_profile_analysis.ipynb` |
| Desktop playground | `notebooks/lakeside_desktop_sim_playground.ipynb` |

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
