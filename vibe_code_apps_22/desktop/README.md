# Lakeside Heating DSM — desktop (Rust)

Windows egui + ONNX Runtime walk for the 6-Area heating DSM spreadsheet.

## What it does

- Loads `ml/artifacts/heating_dsm_hourly_v1.onnx` + feature meta (trained on
  `ENERGYPLUS_SIMULATED` farm when present).
- 24h facility kW walk from OAT profile, strategy, and per-zone HP on/off.
- Engineering cost playground: **$/kWh** + **$/kW** demand + annual stub.

Midnight zone temps are shown for B2 warm-by-start; current ONNX predicts
**facility_kw only**.

## Build / run

```powershell
cd vibe_code_apps_22\desktop
cargo run --release
```

Optional: `$env:LAKESIDE_ONNX_DIR = "...\ml\artifacts"`

Train artifacts first:

```powershell
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
python scripts\eplus_heating_dsm_farm.py
python -u ml\train_heating_dsm_torch.py
```
