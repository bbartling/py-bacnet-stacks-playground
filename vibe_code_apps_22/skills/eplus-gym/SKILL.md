---
name: eplus-gym
description: >-
  Any-building EnergyPlus DSM gym (vibe22): rule demand-response on the
  published W2A champion via eplus_gym. Lookup farm (eplus/dsm_farm_w2a) or
  live EnergyPlus via CLI (scripts/vibe22.py). Streamlit REMOVED. IdealLoads
  farm is STRUCTURAL_LOAD_DIAGNOSTIC and CLI-only. Practice pack: Lakeside /
  sp_creekside (A04).
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

- W2A champion = `W2A_PHYSICAL_DSM`
- IdealLoads = `STRUCTURAL_LOAD_DIAGNOSTIC` (CLI screening only)
- Lookup = `FARM_LOOKUP_EMULATOR` (not closed-loop)
- Live = `ENERGYPLUS_PYTHON_API` (Gym Runtime / CLI)
- Claim: **ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY**
- `promote=False`
- W2A `auto` **never** falls back to IdealLoads `dsm_farm_paired`

## CLI entrypoint (Streamlit REMOVED)

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"  # practice
python -u scripts\vibe22.py status --site-root $env:SITE_ROOT
python -u scripts\vibe22.py optimize-day --day 2026-01-26 --lookback-days 3 --budget 8 --no-cache --simulator LIVE_ENERGYPLUS
```

Six-zone actuation (staged DualSP schedules `DSM_HTG_SP_*`) must PASS
`scripts/gate_six_zone_actuation.py` before optimization.

Site Config JSON: `{SITE}/reports/eplus_gym/site_dsm_config.json` — patches
**staged** IDFs only.

## Modes

| Mode | Provenance |
| --- | --- |
| lookup | `FARM_LOOKUP_EMULATOR` |
| live | `ENERGYPLUS_PYTHON_API` |

## Guardrails

- Never mutate published champion IDF
- No BACnet writes
- Approve writes only `approved_recommendation.json`
- PHYSICAL_ONLY default — illustrative $ never selects
