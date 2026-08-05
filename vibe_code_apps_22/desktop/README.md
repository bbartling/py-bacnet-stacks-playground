# Lakeside Heating DSM — desktop (Rust)

Windows egui + ONNX Runtime walk for the 6-Area heating DSM spreadsheet.

## What it does

- Loads `ml/artifacts/heating_dsm_hourly_v1.onnx` + feature meta (trained on
  `ENERGYPLUS_SIMULATED` farm when present).
- 24h facility kW walk from OAT profile, strategy, and per-zone HP on/off.
- **Load utility bill CSV** → validate columns (aliases OK) → OLS **$/kWh + $/kW**
  with industry guardrails; graceful error banner if the file is wrong.

Midnight zone temps are shown for B2 warm-by-start; current ONNX predicts
**facility_kw only**.

## Utility bill CSV

Schema + aliases: [`../data/sample/UTILITY_BILL_CSV.md`](../data/sample/UTILITY_BILL_CSV.md)  
Sample: `../data/sample/utility_bills_demand_sample.csv`

Also auto-loads (first hit wins):

1. `$env:LAKESIDE_UTILITY_BILLS_CSV`
2. `$LAKESIDE_SITE_ROOT/utilities/electricity_utility_demand.csv`
3. `$LAKESIDE_SITE_ROOT/utilities/utility_bills_raw.csv`
4. Repo sample CSV

Bad headers / empty Use / Cost≤0 / absurd derived rates → **red error**, rates unchanged.

## Build / run

```powershell
cd vibe_code_apps_22\desktop
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
cargo run --release
```

Optional: `$env:LAKESIDE_ONNX_DIR = "...\ml\artifacts"`

Train artifacts first:

```powershell
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
python scripts\eplus_heating_dsm_farm.py
python -u ml\train_heating_dsm_torch.py
```
