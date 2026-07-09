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

## Environment

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
- [BRANCH_RECONCILIATION_STREAMLIT_MERGE.md](docs/BRANCH_RECONCILIATION_STREAMLIT_MERGE.md)
