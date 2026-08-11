---
name: lakeside-site-pack
description: >-
  Ingest a Lakeside / vibe22 site pack (zip or folder): find campus.json + bill
  CSVs, IDF, interval CSV, optional WattLab dump; publish site_ui_bundle_v1.
  Prefer billing campus_utility.json. Use when an agent must load data for the
  human DSM console or when the user drops a zip.
---

# Lakeside site pack

**Code:** `eplus_gym_app/site_pack.py` · `scripts/ingest_site_pack.py`  
**SoT:** [`../../vibe22_agent_spec/AGENT_LOOP.md`](../../vibe22_agent_spec/AGENT_LOOP.md)

This is a **scanner**, not a WattLab clone. vibe20 uses two zips (dump + energy-use);
a mixed zip is fine if `campus.json` + bills + an `.idf` are inside.

## Required vs recommended

| Gate | Artifacts |
| --- | --- |
| Fuel | `campus.json` / `campus_utility.json` + sibling bill CSVs (`Campus.from_json` must succeed) |
| Twin | one `.idf` (prefer `*a04*` / champion pin) |
| Actual | interval CSV (`demand_vs_web_weather_hourly.csv` or timestamp + kW) |
| Recommended | WattLab `MANIFEST.json` + `data_model.csv` / `model_seed.json`, scorecard, Open-Meteo AMY `.epw` (`eplus_fetch_open_meteo_epw.py`) |

**Billing campus wins** over interval-integrated `campus.json`.

## Run

```powershell
cd vibe_code_apps_22
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
python -u scripts\ingest_site_pack.py --src PATH\to\pack.zip
python -u scripts\ingest_site_pack.py --src PATH\to\folder --inventory-only
```

Writes `{site}/reports/site_ui_bundle_v1.json` with `current_model_id`,
`dsm_champion=A04`, `dsm_farm_parquet=eplus/dsm_farm_w2a/...`.

Human Streamlit sidebar has an optional **Load site pack** expander. Prefer this CLI.

Missing / stale AMY: `python -u scripts\eplus_fetch_open_meteo_epw.py`
(site lat/lon from `eplus/assumptions/answers.json`). See
[`../lakeside-open-meteo-epw/SKILL.md`](../lakeside-open-meteo-epw/SKILL.md).
Do not invent EPW from BAS OAT and do not copy Chicago as TMY.

## Do not

- Ask the human to pick IDF / campus / interval files
- Default fuel to interval-integrated `campus.json` when `campus_utility.json` exists
- Import `wattlab` from vibe20 (use cloned `eplus_gym_app/campus_fuel.py`)
- Treat pack ingest as a live EnergyPlus run
