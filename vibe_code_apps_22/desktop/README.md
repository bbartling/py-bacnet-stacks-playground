# Lakeside Heating DSM — desktop (Rust)

Windows egui + ONNX Runtime walk for the 6-Area heating DSM spreadsheet.

## What it does

- Loads `heating_dsm_hourly_v1.onnx` + feature meta (bake-off champion from
  `ENERGYPLUS_NATIVE_RUN` native farm on the site Lakeside staged twin).
- Shows **model name, tuned params, MAE/RMSE, ± peak MAE** in the UI.
- 24h facility kW walk from OAT profile, strategy, and per-zone HP on/off.
- **Load utility bill CSV** → validate columns (aliases OK) → OLS **$/kWh + $/kW**.

Desktop predicts **`facility_kw` only** (not multi-output).

## Client package (zip for stakeholders)

One command builds a self-contained Windows folder + zip (exe + model + sample bills):

```powershell
cd vibe_code_apps_22\desktop
.\pack_client.ps1
```

Output:

```text
desktop\dist\lakeside-heating-dsm-windows-YYYYMMDD-<champion>\
desktop\dist\lakeside-heating-dsm-windows-YYYYMMDD-<champion>.zip
```

Send the **`.zip`** to the client. They unzip and double-click
`lakeside-heating-dsm.exe` (keep the ONNX/meta files beside the exe).

See [`CLIENT_README.md`](CLIENT_README.md) (also copied into the zip).

```powershell
.\pack_client.ps1 -SkipBuild   # reuse existing target\release exe
```

## Utility bill CSV

Schema + aliases: [`../data/sample/UTILITY_BILL_CSV.md`](../data/sample/UTILITY_BILL_CSV.md)  
Sample: `../data/sample/utility_bills_demand_sample.csv`

Also auto-loads (first hit wins):

1. `$env:LAKESIDE_UTILITY_BILLS_CSV`
2. `$LAKESIDE_SITE_ROOT/utilities/electricity_utility_demand.csv`
3. `$LAKESIDE_SITE_ROOT/utilities/utility_bills_raw.csv`
4. `utility_bills_demand_sample.csv` next to the `.exe` (client zip)
5. Repo sample CSV (dev)

## Build / run (developers)

```powershell
cd vibe_code_apps_22\desktop
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
cargo run --release
```

Train / refresh ONNX first:

```powershell
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
python -u ..\ml\train_heating_dsm.py
# or: jupyter notebook ..\notebooks\lakeside_heating_dsm_sklearn.ipynb  (section 8)
```
