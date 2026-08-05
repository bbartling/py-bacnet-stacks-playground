# 2026-08-05 — Sklearn ExtraTrees ONNX for Rust desktop

## Goal

Ship the better sklearn ExtraTrees surrogate into the existing Rust egui+ort desktop
(not a Python GUI). Beef ExtraTrees RandomizedSearch for heating DSM tabular data.

## Design

1. Expand ExtraTrees search space + dedicated higher `n_iter` in `train_heating_dsm.py`.
2. Export tuned ExtraTrees → `heating_dsm_hourly_v1.onnx` via `skl2onnx`
   (input `features`, output `facility_kw`). Raw-feature model + identity scaler in meta
   so Rust `scale_features` stays a no-op without double-scaling.
3. Copy onnx+meta into `desktop/artifacts/` for release-adjacent runs.
4. Torch export moves to `heating_dsm_hourly_torch_v1.*` so it does not clobber ship.
5. Rust banner shows family / champion / training_source honesty.

## Out of scope

Multitarget zone-temp desktop, Python desktop app.
