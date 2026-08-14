---
name: open-meteo-epw
description: >-
  Fetch Open-Meteo archive weather at any vibe22 site lat/lon and write an
  EnergyPlus AMY EPW as {slug}_amy_*.epw. Practice pack: Lakeside / sp_creekside.
  Use when AMY is missing, stale, or the user asks for actual-year weather.
---

# Open-Meteo → AMY EPW

**Code:** `eplus_gym_app/open_meteo_epw.py`  
**CLI:** `scripts/eplus_fetch_open_meteo_epw.py`  
(alias: `scripts/eplus_build_amy_epw.py`)  
**SoT:** [`../../vibe22_agent_spec/EPLUS_GYM.md`](../../vibe22_agent_spec/EPLUS_GYM.md) ·
[`../../vibe22_agent_spec/DATA_CONTRACT.md`](../../vibe22_agent_spec/DATA_CONTRACT.md)

## Honesty

| File | What it is | What it is not |
| --- | --- | --- |
| `{slug}_amy_*.epw` | **AMY** = Open-Meteo **actual year** at site lat/lon (M&V) | Not TMY. Not "typical." |
| Site `*TMY*.epw` | Typical year (download separately) | Not auto-built from Open-Meteo |
| `*screening*.epw` / Chicago O'Hare | Screening stand-in only | **Never** auto-pick as TMY |

Do **not** build an EPW from BAS OAT-only. EnergyPlus needs dry-bulb, dewpoint,
RH, pressure, GHI/DNI/DHI, and wind. Open-Meteo archive supplies those.

## Agent tool

Geo comes from `{site}/eplus/assumptions/answers.json` or campus (`lat`, `lon`,
`data_window`). Window end extends to Open-Meteo archive lag (~3 days behind
today) unless you pass `--end`. `slug` = `site_slug()` (campus_id or folder).

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_22
$env:SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"  # practice
python -u scripts\eplus_fetch_open_meteo_epw.py
python -u scripts\eplus_fetch_open_meteo_epw.py --force
python -u scripts\eplus_fetch_open_meteo_epw.py --start 2025-08-01 --end 2026-08-08
```

Writes:

- `eplus/weather/{slug}_amy_YYYYMM_YYYYMM.epw`
- `eplus/weather/open_meteo_amy_hourly.csv`
- `eplus/weather/amy_meta.json` (`source=open-meteo-archive`, `kind=AMY_OPEN_METEO`)

Skips the network if the existing AMY already covers `(today − 5 days)`.
`--force` refetches. Old dated AMY files are pruned; Chicago screening is never
copied. Historical practice files may still be named `madison_amy_*.epw`.

## When to run

- Live DSM / GL14 and no `*_amy*.epw`
- Existing AMY ends before the BAS / requested sim window
- User asks for fresh Open-Meteo / actual-year weather

## Do not

- Fetch TMY from Open-Meteo (wrong product)
- Copy `USA_IL_Chicago*` or `*screening*.epw` into the TMY slot
- Invent solar/RH/wind from the interval meter
- Invent lat/lon when campus/answers lack them
- Point Streamlit file pickers at weather (pack ingest + this tool only)
