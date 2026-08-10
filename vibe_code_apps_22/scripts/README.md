# vibe22 scripts map

**Train / ship SoT (2026-08-07):** CLI, not Jupyter kernels.

| Script | Role |
| --- | --- |
| `train_four_arms.py` | Parallel sklearn/torch × winter/allyear → `ml/artifacts/runs/` |
| `train_arm.py` | One arm worker (spawned by four-arm launcher) |
| `ship_best_to_desktop.py` | Pick best sklearn arm (held-out peak MAE only) → promote → `cargo run --release`; `--allow-smoke-promote` for &lt;12 pairs |
| `promote_hybrid_ship.py` | Hybrid walk + copy into `desktop/artifacts/` (smoke &lt;12 pairs needs `VIBE22_ALLOW_SMOKE_PROMOTE=1` or ship `--allow-smoke-promote`) |
| `validate_eplus_multires.py` | Monthly / hourly / 15-min DSM multi-res validation JSON |
| `_gen_results_viewer_notebooks.py` | Regen sklearn/torch **viewer** notebooks |
| `_gen_load_profile_analysis_nb.py` | Regen load-profile analysis notebook |
| `_gen_desktop_sim_playground_nb.py` | Regen desktop ONNX playground notebook |

## Data / farm / desktop helpers (live)

| Script | Role |
| --- | --- |
| `build_real_15min_store.py` | Real BAS parquet store |
| `eplus_heating_dsm_farm.py` | Paired E+ DSM farm (`--crossed` / `--pre-roll-days` / weather fail-closed) |
| `eplus_w2a_dsm_farm_scaffold.py` | Stage W2A_PHYSICAL_DSM IDF copy (no champion overwrite) |
| `spinup_sensitivity.py` | Pre-roll 0/3/7/14 scaffold CSV (`--from-farm-root`) |
| `timestep_sensitivity.py` | Timestep 4/6/12 scaffold (`--stage-w2a`) |
| `inventory_greybox_sensors.py` | Grey-box sensor manifest (UNKNOWN ok) |
| `train_greybox_shadow_v1.py` | One-zone 1R1C GREYBOX_SHADOW_V1 fit (NON_PROMOTABLE; no hybrid retrain) |
| `export_nearest_day_library.py` | Nearest-day library for desktop |
| `export_control_contracts.py` | Control strategy contracts |
| `validate_mvm.py` | MVM hourly + 15-min (delegates formulas to `ml/eplus_multires_metrics`) |
| `eplus_calibrate_multires.py` | Versioned multi-res calibration campaign runner |
| `demand_weather_charts.py` | Load/weather analytics PNGs |
| E+ / OpenStudio / utility scripts | Calibration + GL14 campaign |

## Legacy (keep for delta retrain / emergency)

| Script | Role |
| --- | --- |
| `run_sklearn_tutorial_train.py` | Single-process A (baseline) + B (delta) + optional smoke promote. Prefer `train_four_arms` for baselines; use this when **retraining delta**. |

## Removed (dead)

- `_gen_tutorial_notebooks.py` — regenerated in-kernel **train** notebooks (clobbered viewers)
- `_run_tutorial_notebooks.py` / `_exec_tutorial_nb.py` — executed train-in-notebook
- `_lean_cli_regen.py` — one-off lean regen → replaced by `train_arm`
- `run_torch_tutorial_train.py` — replaced by `train_arm --arm torch_*`
