# ml/ — thin shared helpers (post gym cut)

Product control path is [`../eplus_gym/`](../eplus_gym/). This folder keeps small
shared utilities used by twin scripts and the gym:

| Module | Role |
|---|---|
| `interval15.py` | Canonical 15-min clock |
| `physics_families.py` | `STRUCTURAL_LOAD_DIAGNOSTIC` / `W2A_PHYSICAL_DSM` |
| `artifact_paths.py` | Path helpers (site + legacy keys) |
| `site_weather.py` | Weather attach helpers |
| `energy_math.py` | Energy integrals |
| `notebook_plots.py` | Theme helpers |
| `eplus_multires_metrics.py` / `eplus_validation_contract.py` | Multi-res gates |
| `chrono_splits.py` / `timing_utils.py` / `eplus_calib_diagnostics.py` | Calibrate support |

Hybrid train/rollout/ONNX modules → [`../archive/2026-08-10_pre_eplus_gym/ml_modules/`](../archive/2026-08-10_pre_eplus_gym/ml_modules/).
