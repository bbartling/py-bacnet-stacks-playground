---
name: lakeside-heating-dsm
description: >-
  Lakeside Elementary heating demand-side management ML (vibe22): 6-Area HP
  occupancy/preheat scenarios, morning peak HE 05–09, sklearn ExtraTrees→ONNX
  desktop, Excel cost playground. Use when working on vibe_code_apps_22,
  heating DSM, stagger preheat, facility_kw surrogate, or Lakeside demand peaks.
---

# Lakeside heating DSM (vibe22)

**Code:** `vibe_code_apps_22/`  
**Site data:** `LAKESIDE_SITE_ROOT` → typically
`C:\Users\ben\OneDrive\Desktop\testing\sp_creekside`

## Goal

Hourly `facility_kw` under weather + 6-Area occupancy knobs for **morning peak**
management (not Liberty cooling DR / vibe21).

## Run

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
python -u scripts\eplus_heating_dsm_farm.py   # preferred ENERGYPLUS_SIMULATED
python -u ml\train_heating_dsm.py             # ExtraTrees → ONNX ship
cd desktop; cargo run --release               # $/kWh + $/kW walk + model card
```

Fallback: `ml\build_bootstrap_dataset.py` if no farm yet.

Notebook: `notebooks/lakeside_heating_dsm_sklearn.ipynb`

## Honesty

Prefer `ENERGYPLUS_SIMULATED` (IdealLoads+COP farm on pinned G14 twin). Fallback
`BAS_BOOTSTRAP_PROXY`. Status `CANDIDATE` — not tariff-grade. Zone-temp
multi-target (warm-by-start) is Phase B2.

## Key modules

- `scripts/eplus_heating_dsm_farm.py`
- `ml/feature_compile_heating_dsm.py` (`cost_from_hourly_kw`)
- `ml/seed_proxy_scenarios.py`
- `ml/train_heating_dsm.py` / `ml/export_sklearn_onnx.py`
- `desktop/` — Rust egui + ONNX (model name, params, MAE/RMSE, ± band)
- `lakeside/paths.py`
