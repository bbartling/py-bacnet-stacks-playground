---
name: site-pack
description: >-
  Ingest any-building / vibe22 site pack (zip or folder): find campus.json + bill
  CSVs, IDF, interval CSV, optional WattLab dump; publish site_ui_bundle_v1.
  Prefer billing campus_utility.json. Practice pack: Lakeside / sp_creekside.
  Use when an agent must load data for the human DSM console or when the user
  drops a zip.
---

# Site pack (any building)

**Code:** `eplus_gym_app/site_pack.py` · `scripts/ingest_site_pack.py`  
**SoT:** [`../../vibe22_agent_spec/AGENT_LOOP.md`](../../vibe22_agent_spec/AGENT_LOOP.md) ·
[`../../vibe22_agent_spec/DATA_CONTRACT.md`](../../vibe22_agent_spec/DATA_CONTRACT.md)

Practice pack: Lakeside ES / `sp_creekside` (research name Creekside). Product
path is data-model driven for **any** site.

This is a **scanner**, not a WattLab clone. vibe20 uses two zips (dump + energy-use);
a mixed zip is fine if `campus.json` + bills + an `.idf` are inside.
**vibe19 does not write `campus.json`** — energy campus is separate.

## Required vs recommended

| Gate | Artifacts |
| --- | --- |
| Fuel | `campus.json` / `campus_utility.json` + sibling bill CSVs (`Campus.from_json` must succeed) |
| Twin | one `.idf` (prefer champion pin from catalog / name) |
| Actual | interval CSV (`demand_vs_web_weather_hourly.csv` or timestamp + kW) |
| Recommended | WattLab `MANIFEST.json` + `data_model.csv` / `model_seed.json`, scorecard, Open-Meteo AMY `.epw` |

**Billing campus wins** over interval-integrated `campus.json`.

## Run

```powershell
cd vibe_code_apps_22
$env:SITE_ROOT="PATH\to\site"   # or LAKESIDE_SITE_ROOT for practice
python -u scripts\ingest_site_pack.py --src PATH\to\pack.zip
python -u scripts\ingest_site_pack.py --src PATH\to\folder --inventory-only
```

Writes `{site}/reports/site_ui_bundle_v1.json` with `current_model_id`,
`dsm_champion` (from pack), `dsm_farm_parquet=eplus/dsm_farm_w2a/...` when present.

Human Streamlit sidebar may offer **Load site pack**. Prefer this CLI.

Missing / stale AMY: `python -u scripts\eplus_fetch_open_meteo_epw.py`
(site lat/lon from `eplus/assumptions/answers.json` / campus). See
[`../open-meteo-epw/SKILL.md`](../open-meteo-epw/SKILL.md).
Do not invent EPW from BAS OAT and do not copy Chicago as TMY.

## Do not

- Ask the human to pick IDF / campus / interval files
- Default fuel to interval-integrated `campus.json` when `campus_utility.json` exists
- Import `wattlab` from vibe20 (use cloned `eplus_gym_app/campus_fuel.py`)
- Treat pack ingest as a live EnergyPlus run
- Hardcode Lakeside / Madison into product code
