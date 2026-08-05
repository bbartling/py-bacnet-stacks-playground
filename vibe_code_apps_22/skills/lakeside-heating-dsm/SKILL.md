---
name: lakeside-heating-dsm
description: >-
  Lakeside Elementary heating demand-side management ML (vibe22): native
  EnergyPlus IdealLoads+COP farm (ENERGYPLUS_NATIVE_RUN), 6-Area HP
  occupancy/preheat, morning peak HE 05–09, sklearn bake-off→ONNX desktop,
  measured-vs-modeled validation. Use for vibe_code_apps_22 heating DSM.
---

# Lakeside heating DSM (vibe22)

**Code:** `vibe_code_apps_22/`  
**Site data:** `LAKESIDE_SITE_ROOT` → typically
`C:\Users\ben\OneDrive\Desktop\testing\sp_creekside`

**Human SoT:** `notebooks/lakeside_heating_dsm_sklearn.ipynb` (provenance scoreboard).  
**Engineering report:** `vibe22_agent_spec/NATIVE_EPLUS_DSM_REPORT.md`

## Goal

Hourly `facility_kw` under weather + 6-Area occupancy knobs for **morning peak**
management (not Liberty cooling DR / vibe21).

## Run (production — native E+ only)

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
$env:PYTHONUNBUFFERED="1"

# 1) Stage-repair utility champion → 0 severe + monthly GL14 re-score
python -u scripts\eplus_stage_repair_and_rescore.py

# 2) Native farm (fail-closed; resumes by input hash)
python -u scripts\eplus_heating_dsm_farm.py --smoke    # ~12 runs
python -u scripts\eplus_heating_dsm_farm.py --medium   # ~80–120+ scenario-days

# 3) Measured vs modeled (hourly / monthly GL14 separate)
python -u scripts\validate_mvm.py

# 4) Train → desktop ONNX
python -u ml\train_heating_dsm.py
# or re-run notebooks\lakeside_heating_dsm_sklearn.ipynb top-to-bottom

cd desktop; cargo run --release
# Client zip: .\pack_client.ps1
```

**DEMO only** (not production): `$env:LAKESIDE_DEMO_NOT_ENERGYPLUS="1"` then bootstrap.
`train_parquet_path()` **fails closed** without `ENERGYPLUS_NATIVE_RUN` farm.

## Honesty

| Tag | Role |
| --- | --- |
| `ENERGYPLUS_NATIVE_RUN` | **Production** — zero severe/fatal native E+ + manifest |
| Ideal Loads + fixed-COP | Electric proxy (COP 3.5/4.5) — **not** GSHP/GLHE plant |
| `BAS_BOOTSTRAP_PROXY` | DEMO / screening only |
| `CANDIDATE` | Registry status until tariff/BAS ops validated |

Monthly utility GL14 ≠ interval demand fidelity. Desktop peak MAE is a
**screening metric**, not an uncertainty interval.

## Key modules

- `eplus_native/` — runner, err parse, validator, meters, align, IDF stage
- `scripts/eplus_stage_repair_and_rescore.py`
- `scripts/eplus_heating_dsm_farm.py` — native farm only
- `scripts/validate_mvm.py`
- `ml/artifact_paths.py` — fail-closed train path
- `ml/train_heating_dsm.py` / `ml/export_sklearn_onnx.py`
- `desktop/` — egui + ONNX + MVM panel + CP-2 tariff
- Staged DSM-eligible IDF: `$SITE/eplus/models/staged/…_dsm_v1.idf` (+ `DSM_ELIGIBLE.json`)
