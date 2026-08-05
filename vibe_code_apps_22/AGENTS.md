# AGENTS.md — Vibe 22 Lakeside Elementary School

**Single code home** for Lakeside ES (southern Wisconsin): ALC → openfdd package,
EnergyPlus IdealLoads G14, utility-bill G14, heating DSM ML, OpenStudio OSM
authoring. **Unity digital twin stays in vibe21** (Liberty) — not this app.

**Read first:** [`vibe22_agent_spec/HEATING_DSM.md`](vibe22_agent_spec/HEATING_DSM.md),
[`vibe22_agent_spec/UTILITY_GL14.md`](vibe22_agent_spec/UTILITY_GL14.md),
[`skills/lakeside-heating-dsm/SKILL.md`](skills/lakeside-heating-dsm/SKILL.md),
[`skills/lakeside-eplus-gl14/SKILL.md`](skills/lakeside-eplus-gl14/SKILL.md),
[`skills/lakeside-utility-gl14/SKILL.md`](skills/lakeside-utility-gl14/SKILL.md),
[`ml/README.md`](ml/README.md).

Site SoT (data, E+ runs, ALC historian): set `LAKESIDE_SITE_ROOT`
(default `…\Desktop\testing\sp_creekside`). This repo holds **code + small artifacts**.

Building id: `LAKESIDE_ES` · `siteRef`: `spasd_lakeside_es`

Last validated: **2026-08-05**.

---

## Mission

1. Process ALC WebCTRL dumps → vibe19 `openfdd_package_v1` + vibe20 utilities.
2. Calibrate IdealLoads twin to ASHRAE G14 (interval + client utility bills).
3. Train heating-startup DSM surrogates (sklearn + PyTorch/ONNX; HE 05–09).
4. Optional OpenStudio OSM authoring (native SDK; no Docker required).
5. Leave room for a future **BACnet** app under `bacnet/` (stub only for now).

---

## Layout

```text
vibe_code_apps_22/
  lakeside/paths.py          # SITE_ROOT + building constants
  scripts/                   # ALC pipe, E+, OpenStudio, DSM Excel
  ml/                        # heating DSM train / features / artifacts
  notebooks/                 # lakeside_heating_dsm_*.ipynb
  dsm/                       # Excel playground + CSV exports
  docs/                      # E+ plan, OpenStudio-MCP notes
  skills/                    # agent skills
  openstudio_mcp_bridge/     # optional Docker MCP (not required)
  bacnet/                    # FUTURE — live BACnet app placeholder
  vibe22_agent_spec/
```

---

## Env

| Var | Purpose |
| --- | --- |
| `LAKESIDE_SITE_ROOT` | Preferred site data root |
| `VIBE22_SITE_ROOT` | Alias |
| `VIBE22_CREEKSIDE_ROOT` / `VIBE23_CREEKSIDE_ROOT` | Legacy aliases |

OpenStudio SDK (if used): `{SITE}/tools/openstudio/sdk/…`

---

## Run order

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
$env:PYTHONUNBUFFERED="1"
$env:PYTHONIOENCODING="utf-8"
pip install -r requirements.txt

# ALC → package (writes into SITE)
python -u scripts\process_lakeside.py
python -u scripts\demand_weather_charts.py
python -u scripts\thermal_zone_analytics.py

# E+ targets / campaigns (needs local EnergyPlus; do not resim unless asked)
python -u scripts\eplus_observed_targets.py
# python -u scripts\eplus_campaign_utility.py

# Heating DSM ML
python -u ml\build_bootstrap_dataset.py
python -u ml\train_heating_dsm.py
python -u ml\train_heating_dsm_torch.py
python -u scripts\build_dsm_excel.py

# Notebooks
jupyter notebook notebooks\lakeside_heating_dsm_sklearn.ipynb
```

---

## Honesty

- IdealLoads + COP proxy ≠ full GSHP/GLHE plant.
- Geometry = rectangular program massing, not CAD.
- Heating DSM bootstrap rows are `BAS_BOOTSTRAP_PROXY` until an E+ DM farm exists.
- Utility G14 ≠ interval-integrated G14.
- Display name **Lakeside**; weather station may still be Madison (southern WI).

---

## Relationship

| Vibe | Role |
| --- | --- |
| 19 | Open-FDD consumer of `LAKESIDE_ES` package |
| 20 | WattLab / utility campus JSON |
| 21 | Unity + Flask demand twin (Liberty) — separate |
| **22** | **All Lakeside code (this app)** |
