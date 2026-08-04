---
name: creekside-heating-dsm
description: >-
  Creekside Elementary heating demand-side management ML (vibe22): 6-Area HP
  occupancy/preheat scenarios, morning peak HE 05–09, sklearn + PyTorch/ONNX
  surrogates, Excel cost playground. Use when working on vibe_code_apps_22,
  heating DSM, stagger preheat, facility_kw surrogate, or Creekside demand peaks.
---

# Creekside heating DSM (vibe22)

**Repo path:** `vibe_code_apps_22/`  
**Site data:** `VIBE22_CREEKSIDE_ROOT` → typically
`C:\Users\ben\OneDrive\Desktop\testing\sp_creekside`

## Goal

Hourly `facility_kw` under weather + 6-Area occupancy knobs for **morning peak**
management (not Liberty cooling DR / vibe21).

## Run

```powershell
cd vibe_code_apps_22
$env:VIBE22_CREEKSIDE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
python -u ml\build_bootstrap_dataset.py
python -u ml\train_heating_dsm.py
python -u ml\train_heating_dsm_torch.py
```

## Honesty

`BAS_BOOTSTRAP_PROXY` · status `CANDIDATE`. G14 IdealLoads twin lives in
`sp_creekside/eplus/` (~1–2 h agent session to G14 after BAS twin existed).

## Key modules

- `ml/feature_compile_heating_dsm.py`
- `ml/seed_proxy_scenarios.py`
- `notebooks/creekside_heating_dsm_sklearn.ipynb`
- `notebooks/creekside_heating_dsm_pytorch_onnx.ipynb`
- `dsm/creekside_zone_dsm_playground.xlsx`
