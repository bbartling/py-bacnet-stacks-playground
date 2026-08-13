---
name: eplus-gym
description: >-
  Any-building EnergyPlus DSM gym (vibe22): rule demand-response on the
  published W2A champion via eplus_gym. Lookup farm (eplus/dsm_farm_w2a) or
  live EnergyPlus via CLI subprocess. Streamlit Run DSM never binds pyenergyplus
  in-process. IdealLoads farm is STRUCTURAL_LOAD_DIAGNOSTIC and CLI-only.
  Practice pack: Lakeside / sp_creekside (A04).
---

# E+ gym (vibe22)

**Code:** `vibe_code_apps_22/eplus_gym/`  
**Site:** `SITE_ROOT` (alias `LAKESIDE_SITE_ROOT`)  
**SoT:** [`../../vibe22_agent_spec/EPLUS_GYM.md`](../../vibe22_agent_spec/EPLUS_GYM.md) ·
[`../../vibe22_agent_spec/AGENT_LOOP.md`](../../vibe22_agent_spec/AGENT_LOOP.md) ·
weather: [`../open-meteo-epw/SKILL.md`](../open-meteo-epw/SKILL.md)

**Do not** revive hybrid ONNX / grey-box / control-twin lab from
`archive/2026-08-10_pre_eplus_gym/` into the live path.

## Honesty

- W2A champion = `W2A_PHYSICAL_DSM` (human DSM console)
- IdealLoads = `STRUCTURAL_LOAD_DIAGNOSTIC` (CLI screening only)
- Lookup = `FARM_LOOKUP_EMULATOR` (not closed-loop)
- Live = `ENERGYPLUS_PYTHON_API` (via CLI subprocess from Streamlit)
- `promote=False`
- W2A `auto` **never** falls back to IdealLoads `dsm_farm_paired`

## Human console

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"  # practice
streamlit run eplus_gym_app\streamlit_app.py --server.port 8765
```

Tabs: **Site Config** · **Run DSM** · **Calibration** · **Fuel** · **ECMs**.  
No IDF / campus / interval pickers. Pack comes from `ingest_site_pack.py`.

## DSM campaign supervisor

Live Run DSM starts `scripts/run_dsm_campaign.py` once (Popen). Streamlit only
polls `{SITE_ROOT}/reports/eplus_gym/current_dsm_run.json` via `@st.fragment`.
Preflight (EPW span ⊆ coverage, year-aware DATA PERIODS, IDF hash, max_steps)
runs **before** any EnergyPlus child. Defaults: Peak day · AMY · baseline + one
strategy. Cancel writes `cancel_dsm_run.request`. `last_dsm_run.json` updates
only after all jobs validate.

**Site Config:** `{SITE_ROOT}/reports/eplus_gym/site_dsm_config.json` drives
staged-only `SCH_HtgSP` / `SCH_ClgSP` patches (never overwrite champion).

**Weather:** AMY = Open-Meteo actual year (M&V). Refresh with
`python -u scripts\eplus_fetch_open_meteo_epw.py`. Multi-year AMY requires
`DATA PERIODS` with `mm/dd/yyyy` (preflight repairs legacy `mm/dd` headers).
Staged RunPeriods with years set Treat Weather as Actual=Yes.
Never auto-pick Chicago screening as TMY. See `open-meteo-epw`.

**EnergyPlus-MCP (agent only):** use Cursor MCP `user-energyplus` for
`inspect_schedules` / `modify_run_period` / `validate_idf` / `list_zones` on
copies. MCP cannot write live `SCH_HtgSP` actuators — closed-loop stays on
CLI gym. Checklist: `eplus_gym_app/eplus_mcp_bridge.py`.

**Run DSM:** lookup if `{site}/eplus/dsm_farm_w2a` exists; else live via
**subprocess** to `scripts/run_eplus_gym_rules.py --family w2a --mode live`.  
Do **not** import `pyenergyplus` inside the Streamlit server.  
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

Never overwrite IdealLoads `*_best_utility.idf` or the pack W2A champion. See
`eplus-gl14` / `w2a-plant-dial` / `site-pack`.
