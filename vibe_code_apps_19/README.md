# Vibe Code App 19 — Streamlit FDD demo (50-rule pandas cookbook)

Lightweight **Python + Streamlit + pandas** educational app implementing the **full 50-rule Open-FDD pandas cookbook** for BUILDING_100-style CSV data.

**This is not Open-FDD.** Production Rust/DataFusion engine: [Open-FDD](https://github.com/bbartling/open-fdd) (`C:\Users\ben\Documents\open-fdd`).

## What this app is

- All **50 cookbook rules** in readable pandas (`app/rules/cookbook_catalog.py`)
- Streamlit UI with tunable sliders, rule inventory, engineer notes
- Manual YAML role mapping — no Haystack/Oxigraph
- CSV tree, multi-file upload, local folder, read-only SQLite/DuckDB/SQL Server, optional Parquet
- Multi-site / building / equipment nested YAML mapping (Haystack-*like*, no RDF)
- Explicit statuses: `PASS`, `FAULT`, `SKIPPED_MISSING_ROLES`, `NOT_APPLICABLE_EQUIPMENT_TYPE`, `ERROR`

## What this app is not

- Not Rust, DataFusion, FastAPI, or Docker deploy product stack
- Not full Open-FDD SQL parity (19 SQL rules live in Open-FDD)

## Quick start

```powershell
cd vibe_code_apps_19
python -m pip install -e ".[dev]"
streamlit run streamlit_app.py
```

In the sidebar, choose **Upload CSV files** and pick one or more CSVs (no env vars needed). Optional: paste a BUILDING tree path, or set `HVAC_DATA_ROOT`.

## How data maps to rules (automatic)

Rules never use raw vendor column names. They need **logical roles** (`sat`, `zone_t`, `oa_t`, …).

```
CSV headers / columns.csv  →  column map JSON or YAML  →  logical roles on the DataFrame  →  50 cookbook rules
```

1. **Heuristic / `columns.csv`** — `point_role` + header patterns (`app/role_map.py`)
2. **JSON column map** — portable file an LLM can author (`configs/building_100_column_map.json`)
3. **UI** — **Data & Mapping** tab: load/upload JSON, or **Auto-build JSON map from loaded CSVs**

Missing roles → rule status `SKIPPED_MISSING_ROLES` (safe), not a crash.

### Generate map for BUILDING_100

```powershell
python scripts/generate_building100_column_map.py --run-rules
```

### LLM prompt (paste with your column lists)

**Expectation:** humans load any building folder; Claude / Cursor / a local LLM returns a **JSON column map** (not a modified CSV). One JSON covers many AHUs + VAVs. `building_id` is the folder name you loaded (demo data may be called `BUILDING_100`, but nothing in the prompt requires that name).

The Streamlit **Data & Mapping** tab builds a filled prompt (instructions + every loaded equipment’s columns) with a code-block copy control and a `.txt` download. Base template: `LLM_COLUMN_MAP_PROMPT` in `app/column_map_json.py`. Ask the model for JSON only:

```json
{
  "version": 1,
  "building_id": "<your building folder name>",
  "generated_by": "llm",
  "notes": "…",
  "equipment": {
    "AHU_1": {
      "equipment_type": "AHU",
      "column_roles": { "sat": "discharge_air_temp_f", "oa_t": "outside_air_temp_f" }
    }
  }
}
```

Then upload that JSON in the UI or save under `configs/`.

## Environment (optional)

| Variable | Default |
| --- | --- |
| `HVAC_DATA_ROOT` | `./data/hvac_systems_CLEANED` |
| `HVAC_BUILDING` | `BUILDING_100` |

## Rules

See [docs/STREAMLIT_RULE_INVENTORY.md](docs/STREAMLIT_RULE_INVENTORY.md) for canonical count reconciliation.

Regenerate inventory/defaults:

```powershell
python scripts/generate_rule_configs.py
```

## Tests

```powershell
python -m pytest -q
python scripts/validate_building100.py
```

## Docs

- [STREAMLIT_DEMO_SPEC.md](docs/STREAMLIT_DEMO_SPEC.md)
- [STREAMLIT_RULE_INVENTORY.md](docs/STREAMLIT_RULE_INVENTORY.md)
- [MULTI_SITE_CSV_SQL_SPEC.md](docs/MULTI_SITE_CSV_SQL_SPEC.md)
- [CSV_UPLOAD_GUIDE.md](docs/CSV_UPLOAD_GUIDE.md)
- [SQL_SERVER_INPUT_GUIDE.md](docs/SQL_SERVER_INPUT_GUIDE.md)
- [HAYSTACK_LIKE_MAPPING_GUIDE.md](docs/HAYSTACK_LIKE_MAPPING_GUIDE.md)
