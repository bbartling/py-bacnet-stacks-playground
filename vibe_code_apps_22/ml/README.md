# ml/ — thin shared helpers (post gym cut)

Product control path is [`../eplus_gym/`](../eplus_gym/). This folder keeps small
shared utilities used by twin scripts and the gym:

| Module | Role |
|---|---|
| `interval15.py` | Canonical 15-min clock |
| `physics_families.py` | `STRUCTURAL_LOAD_DIAGNOSTIC` / `W2A_PHYSICAL_DSM` |
| `artifact_paths.py` | Path helpers (site weather/demand + farm parquet keys) |
| `site_weather.py` | Weather attach helpers |
| `energy_math.py` | Energy integrals |
| `eplus_multires_metrics.py` / `eplus_validation_contract.py` | Multi-res gates |
| `chrono_splits.py` / `timing_utils.py` / `eplus_calib_diagnostics.py` | Calibrate support |
| `feature_compile_heating_dsm.py` | Farm feature columns (hourly DSM) |
| `run_provenance.py` | Provenance labels |

Hybrid train/rollout/ONNX, `simulation_contract`, `notebook_plots`, `feature_compile_15min`,
and `contracts/hybrid_dsm_96_*.json` → [`../archive/2026-08-10_pre_eplus_gym/`](../archive/2026-08-10_pre_eplus_gym/).
