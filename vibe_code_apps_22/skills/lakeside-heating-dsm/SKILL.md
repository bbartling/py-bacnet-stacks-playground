---
name: lakeside-heating-dsm
description: >-
  Lakeside Elementary hybrid heating DSM (vibe22): real BAS 15-min baseline +
  paired EnergyPlus IdealLoads+COP intervention deltas → 96-step hybrid rollout;
  sklearn (GB/ET/RF) + ResMLP; HYBRID_SCREENING honesty. Use for vibe_code_apps_22.
---

# Lakeside heating DSM (vibe22) — Hybrid Real+E+

**Code:** `vibe_code_apps_22/`  
**Site data:** `LAKESIDE_SITE_ROOT` → typically
`C:\Users\ben\OneDrive\Desktop\testing\sp_creekside`

**Do not** concat real BAS and EnergyPlus rows into one training table.  
**Honesty:** `HYBRID_SCREENING` until field DSM trials. IdealLoads+COP ≠ GSHP plant.

## Pipeline

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
$env:PYTHONUNBUFFERED="1"

# A) Real 15-min store + baseline (7 outs)
python -u scripts\build_real_15min_store.py
python -u ml\train_real_baseline_15min.py --winter-only
python -u ml\train_real_baseline_torch_15min.py --winter-only

# B) Paired E+ farm + delta model
python -u scripts\eplus_heating_dsm_farm.py --smoke
python -u ml\train_eplus_delta_15min.py

# C) Hybrid 96-step + desktop ship
python -u scripts\promote_hybrid_ship.py
python -u scripts\validate_mvm.py   # includes 15-min peak metrics
cd desktop; cargo run --release
```

## Key modules

- `ml/real_store/` — measured 15-min feature store
- `ml/hybrid_rollout.py` + `contracts/hybrid_dsm_96_v1.json`
- `scripts/eplus_heating_dsm_farm.py` — paired baseline/DSM, 6-area controls, MAT
- `eplus_native/align.py` — E+ LST→UTC fixed CST−6 (no DST on E+ stamps)
- `desktop/` — hybrid 96-step panel (fail-closed without walk JSON)

Prior kW-only ship stems live under `ml/artifacts/_quarantine_*`.
