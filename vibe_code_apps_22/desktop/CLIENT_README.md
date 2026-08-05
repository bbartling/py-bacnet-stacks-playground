# Lakeside Heating DSM — desktop walk (client package)

Windows app for a **24-hour facility kW** what-if walk (6 BAS Areas, strategies,
HP on/off) with **$/kWh + $/kW** cost playground.

## Quick start

1. Unzip this folder anywhere (keep all files together).
2. Double-click **`lakeside-heating-dsm.exe`**.
3. Optional: click **Load utility bills CSV…** (or use the included sample).
4. Adjust OAT / strategy / HP grid → **Run 24h ONNX walk**.

Do **not** move the `.exe` away from the `.onnx` / `_feature_meta.json` files —
the model must sit in the **same folder** as the executable.

## What’s included

| File | Role |
| --- | --- |
| `lakeside-heating-dsm.exe` | egui desktop app |
| `heating_dsm_hourly_v1.onnx` | ML surrogate (facility_kW) |
| `heating_dsm_hourly_v1_feature_meta.json` | Feature order, model name, params, MAE/RMSE, ± band |
| `utility_bills_demand_sample.csv` | Example bill CSV for rate derivation |
| `UTILITY_BILL_CSV.md` | Bill CSV column aliases / schema |
| `CLIENT_README.md` | This file |

## Honesty (read this)

- Status: **CANDIDATE** screening tool — **not** tariff-grade or APPROVED.
- Training labels: EnergyPlus IdealLoads + COP proxy farm (`ENERGYPLUS_SIMULATED`)
  unless your package notes otherwise.
- Predicts **facility electric kW only** (not zone air temps yet).
- The ± kW band on the plot is **peak-window MAE** (morning HE 05–09) —
  a screening uncertainty, **not** a formal prediction interval.

The app banner shows the **model name, tuned hyperparameters, and CV metrics**
from the meta file.

## Optional environment

| Variable | Purpose |
| --- | --- |
| `LAKESIDE_ONNX_DIR` | Folder containing the `.onnx` + meta (overrides same-folder lookup) |
| `LAKESIDE_UTILITY_BILLS_CSV` | Path to a bill CSV to auto-load |
| `LAKESIDE_SITE_ROOT` | Site data root (optional; used if bills live under `utilities/`) |

## Support layout

If the model fails to load, confirm these two files are next to the `.exe`:

- `heating_dsm_hourly_v1.onnx`
- `heating_dsm_hourly_v1_feature_meta.json`
