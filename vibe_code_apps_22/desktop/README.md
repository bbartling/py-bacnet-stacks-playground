# Lakeside Heating DSM — desktop (Rust)

Windows egui app for the **Hybrid Real+E+** 15-min × 96 DSM walk.

## What it does

- **Fail-closed** without `hybrid_dsm_96_v1_walk.json` (baseline vs DSM trajectories).
- Honesty stamp: **`HYBRID_SCREENING`** (real BAS baseline + IdealLoads+COP deltas).
- Portable TOD + demand tariff (Creekside CP-2 defaults) for cost compare UI.
- Optional legacy hourly ONNX panel is **not** the ship path (quarantined).

Promote artifacts:

```powershell
python -u ..\scripts\promote_hybrid_ship.py
cd vibe_code_apps_22\desktop
cargo test hybrid_walk_loads --release
cargo run --release
```

## Client package

```powershell
.\pack_client.ps1
```

See [`CLIENT_README.md`](CLIENT_README.md).
