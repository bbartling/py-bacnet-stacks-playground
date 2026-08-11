---
name: lakeside-eplus-gym
description: >-
  Lakeside Elementary EnergyPlus DSM gym (vibe22): rule demand-response on the
  published W2A A04 champion via eplus_gym. Lookup farm (eplus/dsm_farm_w2a) or
  live pyenergyplus. Streamlit Run DSM launches live via CLI subprocess only.
  IdealLoads farm is STRUCTURAL_LOAD_DIAGNOSTIC and CLI-only.
---

# Lakeside E+ gym (vibe22)

**Code:** `vibe_code_apps_22/eplus_gym/`  
**Site:** `LAKESIDE_SITE_ROOT`  
**SoT:** [`../../vibe22_agent_spec/EPLUS_GYM.md`](../../vibe22_agent_spec/EPLUS_GYM.md) ·
[`../../vibe22_agent_spec/AGENT_LOOP.md`](../../vibe22_agent_spec/AGENT_LOOP.md) ·
weather: [`../lakeside-open-meteo-epw/SKILL.md`](../lakeside-open-meteo-epw/SKILL.md)

**Do not** revive hybrid ONNX / grey-box / control-twin lab from
`archive/2026-08-10_pre_eplus_gym/` into the live path.

## Honesty

- W2A A04 = `W2A_PHYSICAL_DSM` (human DSM console)
- IdealLoads = `STRUCTURAL_LOAD_DIAGNOSTIC` (CLI screening only)
- Lookup = `FARM_LOOKUP_EMULATOR` (not closed-loop)
- Live = `ENERGYPLUS_PYTHON_API`
- `promote=False`
- W2A `auto` **never** falls back to IdealLoads `dsm_farm_paired`

## Human console

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
streamlit run eplus_gym_app\streamlit_app.py --server.port 8765
```

Tabs: **Run DSM** · **Calibration**.  
No IDF / campus / interval pickers. Pack comes from `ingest_site_pack.py`.
Calendar month defaults to the BAS **peak-day month**.

**Weather:** AMY = Open-Meteo actual year (M&V). Refresh with
`python -u scripts\eplus_fetch_open_meteo_epw.py`. TMY = Madison MSN only —
never auto-pick Chicago screening. See `lakeside-open-meteo-epw`.

**Run DSM:** lookup if `{site}/eplus/dsm_farm_w2a` exists; else live via
**subprocess** to `scripts/run_eplus_gym_rules.py --family w2a --mode live`.  
Do **not** import `pyenergyplus` inside the Streamlit server (ctypes).  
Still **no** live `pyenergyplus` inside Jupyter.

## CLI

```powershell
python -u scripts\run_eplus_gym_rules.py --family w2a --mode auto
python -u scripts\run_eplus_gym_rules.py --family w2a --mode lookup --day 2026-01-26
python -u scripts\run_eplus_gym_rules.py --family w2a --mode live --epw PATH.epw --idf PATH.idf
# IdealLoads structural only:
python -u scripts\run_eplus_gym_rules.py --family idealloads --mode lookup
```

Live needs EnergyPlus + `ENERGYPLUS_ROOT` + EPW/IDF.

## Controllers

Named strategies from `contracts/control_strategies_v1/*.json` → heating SP °C
on `SCH_HtgSP` (live W2A or IdealLoads) or farm trajectory (lookup).

## Twin pins

Never overwrite IdealLoads `*_best_utility.idf` or W2A A04 champion. See
`lakeside-eplus-gl14` / `lakeside-w2a-plant-dial` / `lakeside-site-pack`.
