# archive/ml — parked E+ helpers (not a live ML product)

The human product is calibrated EnergyPlus + the BOPTEST-shaped DSM console.
There is **no** live ONNX / grey-box / hybrid train path.

These modules stay here so GL14 scoring and the IdealLoads farm scripts still
import (`interval15`, `eplus_multires_metrics`, `eplus_validation_contract`, …).
`lakeside.paths.ensure_eplus_helpers_on_path()` puts this folder on `sys.path`.

Do **not** recreate `vibe_code_apps_22/ml/`.
Do **not** train or ship hybrid models from here.

Hybrid / grey-box / Rust desktop / ONNX →
[`../2026-08-10_pre_eplus_gym/`](../2026-08-10_pre_eplus_gym/).
