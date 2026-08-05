# 2026-08-05 — Sklearn ExtraTrees ONNX desktop ship

## Tasks

1. Add `skl2onnx` (+ `onnxconverter-common`) to requirements; implement `export_sklearn_onnx.py`.
2. Beef ExtraTrees grid + `n_iter_extra_trees` in `bake_off`; call export from `train_heating_dsm.main`.
3. Retarget torch ONNX filenames away from v1 ship stem.
4. Rust: parse `family`/`model_backend` in meta; richer top banner; resolve `desktop/artifacts`.
5. Train, round-trip check, `cargo build --release`, update HEATING_DSM / ml README.
