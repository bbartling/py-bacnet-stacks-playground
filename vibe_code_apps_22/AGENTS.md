# AGENTS.md — Vibe 22 Lakeside Elementary School

**Single code home** for Lakeside ES (southern Wisconsin): ALC → openfdd package,
EnergyPlus IdealLoads G14, utility-bill G14, heating DSM ML (E+ farm → sklearn →
Rust ONNX desktop). **Unity digital twin stays in vibe21** (Liberty) — not this app.

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
3. Train heating-startup DSM surrogates (sklearn ExtraTrees → ONNX; HE 05–09).
4. Leave room for a future **BACnet** app under `bacnet/` (stub only for now).

---

## Layout

```text
vibe_code_apps_22/
  lakeside/paths.py          # SITE_ROOT + building constants
  models/eplus/              # Pinned G14-best IdealLoads IDFs + scorecards (git)
  scripts/                   # ALC pipe, E+, DSM Excel / E+ farm
  ml/                        # heating DSM train / features / artifacts
  desktop/                   # Rust egui + ONNX walk ($/kWh + $/kW)
  notebooks/                 # lakeside_heating_dsm_sklearn.ipynb (ships desktop ONNX)
  dsm/                       # Excel playground + CSV exports
  docs/                      # E+ plan / DSM notes
  skills/                    # agent skills
  bacnet/                    # FUTURE — live BACnet app placeholder
  vibe22_agent_spec/
```

Pinned twins: [`models/eplus/`](models/eplus/) (`lakeside_6zone_gshp_best.idf`,
utility champion, scorecards). Campaign / farm scripts use **site**
`eplus/models/` when present, else these repo pins via `resolve_eplus_model()`.

---

## Env

| Var | Purpose |
| --- | --- |
| `LAKESIDE_SITE_ROOT` | Preferred site data root |
| `VIBE22_SITE_ROOT` | Alias |
| `VIBE22_CREEKSIDE_ROOT` / `VIBE23_CREEKSIDE_ROOT` | Legacy aliases |

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

# Heating DSM ML (same ship path as the sklearn notebook)
python -u ml\build_bootstrap_dataset.py
# Prefer E+ farm when EnergyPlus is installed:
# python -u scripts\eplus_heating_dsm_farm.py
python -u ml\train_heating_dsm.py          # ExtraTrees → desktop ONNX
# or: jupyter notebook notebooks\lakeside_heating_dsm_sklearn.ipynb
python -u scripts\build_dsm_excel.py

# Desktop walk (Rust) — loads heating_dsm_hourly_v1.onnx
# cd desktop && cargo run --release
# Client ZIP (exe + model):  cd desktop; .\pack_client.ps1
```
---

## Honesty

- IdealLoads + COP proxy ≠ full GSHP/GLHE plant.
- Geometry = rectangular program massing, not CAD.
- Heating DSM prefers **`ENERGYPLUS_SIMULATED`** farm rows when present; else
  `BAS_BOOTSTRAP_PROXY` until the farm is built.
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
