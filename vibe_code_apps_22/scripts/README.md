# vibe22 scripts map

**Train / ship SoT (2026-08-07):** CLI, not Jupyter kernels.

| Script | Role |
| --- | --- |
| `train_four_arms.py` | Parallel sklearn/torch × winter/allyear → `ml/artifacts/runs/` |
| `train_arm.py` | One arm worker (spawned by four-arm launcher) |
| `ship_best_to_desktop.py` | Pick best sklearn arm → promote → `cargo run --release` |
| `promote_hybrid_ship.py` | Hybrid walk + copy into `desktop/artifacts/` |
| `_gen_results_viewer_notebooks.py` | Regen sklearn/torch **viewer** notebooks |
| `_gen_load_profile_analysis_nb.py` | Regen load-profile analysis notebook |
| `_gen_desktop_sim_playground_nb.py` | Regen desktop ONNX playground notebook |

## Data / farm / desktop helpers (live)

| Script | Role |
| --- | --- |
| `build_real_15min_store.py` | Real BAS parquet store |
| `eplus_heating_dsm_farm.py` | Paired E+ DSM farm |
| `export_nearest_day_library.py` | Nearest-day library for desktop |
| `export_control_contracts.py` | Control strategy contracts |
| `validate_mvm.py` | MVM hourly + 15-min |
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
