---
name: lakeside-eplus-gym
description: >-
  Lakeside Elementary EnergyPlus control gym (vibe22): rule demand-response on
  IdealLoads twin via eplus_gym (rllib-energyplus-inspired). Lookup farm mode or
  live pyenergyplus step loop. Optional RLlib later. STRUCTURAL_LOAD_DIAGNOSTIC.
  Use for vibe_code_apps_22 after 2026-08-10 product cut.
---

# Lakeside E+ gym (vibe22)

**Code:** `vibe_code_apps_22/eplus_gym/`  
**Site:** `LAKESIDE_SITE_ROOT`  
**SoT:** [`../../vibe22_agent_spec/EPLUS_GYM.md`](../../vibe22_agent_spec/EPLUS_GYM.md)

**Do not** revive hybrid ONNX / grey-box / control-twin lab from
`archive/2026-08-10_pre_eplus_gym/` into the live path.

## Honesty

- IdealLoads = `STRUCTURAL_LOAD_DIAGNOSTIC`
- Lookup = `FARM_LOOKUP_EMULATOR` (not closed-loop)
- Live = `ENERGYPLUS_PYTHON_API`
- `promote=False` — never claim plant DSM savings

## Run

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
pip install -r requirements.txt
python -u scripts\run_eplus_gym_rules.py --mode lookup
python -u scripts\run_eplus_gym_rules.py --mode lookup --month 2026-01
python -u scripts\run_eplus_gym_month_farm.py --months 2026-01,2026-02 --dry-run
streamlit run eplus_gym_app\streamlit_app.py --server.port 8765
```

Notebook: `notebooks/lakeside_eplus_gym_playground.ipynb` — **results viewer only**
(plots `reports/eplus_gym/`). Do **not** run live `pyenergyplus` inside Jupyter
(ctypes callbacks crash Cursor). Streamlit also never starts EnergyPlus.

Live mode needs EnergyPlus + `ENERGYPLUS_ROOT` + EPW/IDF (CLI only):

```powershell
python -u scripts\run_eplus_gym_rules.py --mode live --epw PATH.epw --idf PATH.idf
python -u scripts\run_eplus_gym_month_live.py --month 2026-01 --strategy baseline --max-steps 96
```

## Controllers

Named strategies from `contracts/control_strategies_v1/*.json` → heating SP °C
on `SCH_HtgSP` (live) or farm trajectory (lookup).

## RL later

`eplus_gym/train_rllib.py` is a stub. Follow
[airboxlab/rllib-energyplus](https://github.com/airboxlab/rllib-energyplus) when ready;
do not hard-dep Ray for rule DR.

## Twin pins

Never overwrite IdealLoads `*_best_utility.idf` or W2A A04 champion. See
`lakeside-eplus-gl14` / `lakeside-w2a-plant-dial` skills.
