# Vibe 22 data contract (slim)

Artifacts an agent reads or writes for **any building**. Practice pack:
Lakeside / `sp_creekside`. Breaking shapes requires updating the named tests.

Full WattLab Studio contract (finance, capital plan, Docker Twin) remains in
vibe20 — this file covers what **vibe22 Site DSM** actually consumes.

## 1. vibe19 WattLab dump v3 (input seed)

Produced by vibe19 Export → **Build WattLab dump (zip)**. Schema family:
`wattlab_dump_v3` (`MANIFEST.json` + seed / stats / topology CSVs).

**vibe19 does NOT write `campus.json`.** Campus + bill CSVs come from a separate
energy-use zip/folder, Excel → campus helper, or agent/human authoring under
`utilities/`. Dump may include `utility_bills.csv` / meter monthlies as **hints**
only — still map them into campus + sibling CSVs for Fuel / GL14.

Agent reads `MANIFEST.json` first. Never invent `building_type`, city, floor
area, or lat/lon when the dump marks them `user_required` / missing.

## 2. campus.json (+ bill_columns)

Loaded by cloned `eplus_gym_app/campus_fuel.py` (`Campus.from_json` shape —
**do not import** vibe20 `wattlab`). Prefer billing
`utilities/campus_utility.json` over interval-integrated `utilities/campus.json`.

```json
{
  "campus_id": "my_site",
  "label": "Human label",
  "siteRef": "optional_haystack_site",
  "lat": 42.33,
  "lon": -83.05,
  "bill_columns": {
    "month": "Bill Month",
    "usage": "kWh Total",
    "demand_kw": "Billed Demand (kW)",
    "cost_usd": "Total Current Charges ($)"
  },
  "buildings": [
    {"building_id": "b1", "floor_area_ft2": 140000, "property_type": "office"}
  ],
  "meters": [
    {"meter_id": "elec_1", "fuel": "electricity", "unit": "kwh",
     "file": "electricity.csv",
     "serves": ["b1"],
     "bill_columns": {"month": "Bill Month", "usage": "kWh Total"}}
  ]
}
```

- Optional campus- or meter-level `bill_columns`: logical keys → **exact CSV
  headers**. Heuristics are fallback only.
- Lat/lon (aliases `latitude`/`longitude`) feed Open-Meteo — never invent
  Madison/Chicago/Detroit in code.
- Bill CSVs sit beside campus under `utilities/`.

Tests: `tests/test_campus_pickers.py`, `tests/test_generic_site_pack.py` (when present).

## 3. site_ui_bundle_v1

Published by `eplus_gym_app/site_pack.publish_site_ui_bundle` →
`{SITE_ROOT}/reports/site_ui_bundle_v1.json`.

Humans never pick files; Streamlit binds to this manifest.

| Field | Role |
| --- | --- |
| `schema_version` | `site_ui_bundle_v1` |
| `campus_json` | Relative path to billing campus |
| `bas_demand_oat_csv` | Interval Actual (demand + OAT) |
| `current_model_id` / `dsm_champion` | From pack catalog / IDF (practice A04) |
| `idf_pin` | Champion IDF filename |
| `dsm_farm_parquet` | W2A farm when present |
| `epw` | Preferred AMY path |
| `model_catalog` | Dial ladder entries + IdealLoads structural pins |
| `honesty` | Stamps (`W2A_PHYSICAL_DSM`, `STRUCTURAL_LOAD_DIAGNOSTIC`, …) |

Example contract: `contracts/site_ui_bundle_v1.lakeside.example.json` (practice).  
Tests: `tests/test_site_ui_bundle.py`.

## 4. observed_monthly

GL14 observed series under `{SITE_ROOT}/reports/eplus/`:

| File | Role |
| --- | --- |
| `observed_monthly_utility.csv` | Billing-grade monthly kWh (utility campaign) |
| Interval-derived monthlies | From BAS demand integrate (IdealLoads interval G14) |

Columns typically: `month`, `kwh` (and fuel-specific variants when gas exists).  
Refresh when bills change (`scripts/ingest_utility_bills.py` /
`scripts/eplus_observed_targets.py`).

## 5. ecm_compare.json

Optional agent publish: `{SITE_ROOT}/reports/ecm_compare.json`.

Studio/console ECMs tab reads this (or empty stub). Spreadsheet parity may also
appear as `ecm_full_parity_compare.json` — **never invent** `ss_*` savings numbers.
Shape aligned with vibe20 `wattlab_ecm_compare_v1` when present.

## 6. AMY EPW — `{slug}_amy_*.epw`

Open-Meteo archive → EnergyPlus EPW via `eplus_gym_app/open_meteo_epw.py`:

```text
{SITE_ROOT}/eplus/weather/{slug}_amy_YYYYMM_YYYYMM.epw
{SITE_ROOT}/eplus/weather/open_meteo_amy_hourly.csv
{SITE_ROOT}/eplus/weather/amy_meta.json
```

`slug` = `site_slug()` (`campus_id` or site folder). Practice Lakeside often still
shows historical `madison_amy_*.epw` names on disk — new fetches use the slug.

| Kind | Meaning |
| --- | --- |
| `*_amy_*` | Actual meteorological year (M&V) |
| TMY | Typical year — separate download; never Open-Meteo “TMY” |
| `*screening*` / Chicago O'Hare | Screening only — never auto-pick as TMY |

Do not build EPW from BAS OAT-only.

## Env

| Var | Role |
| --- | --- |
| `SITE_ROOT` | Preferred site workspace |
| `LAKESIDE_SITE_ROOT` | Alias |
| `VIBE22_SITE_ROOT` | Alias |
