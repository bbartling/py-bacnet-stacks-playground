# Vibe Code App 19 — Streamlit FDD demo (50-rule pandas cookbook)

Lightweight **Python + Streamlit + pandas** educational app implementing the **full 50-rule Open-FDD pandas cookbook** for BUILDING_100-style CSV data.

**This is not Open-FDD.** Production Rust/DataFusion engine: [Open-FDD](https://github.com/bbartling/open-fdd) (`C:\Users\ben\Documents\open-fdd`).

## What this app is

- All **50 cookbook rules** in readable pandas (`app/rules/cookbook_catalog.py`)
- Streamlit UI with tunable sliders, rule inventory, engineer notes
- Manual YAML role mapping — no Haystack/Oxigraph
- CSV tree, upload, local folder, read-only SQLite/DuckDB, optional Parquet
- **SKIPPED** status when required roles are missing (never silent omission)

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
- [BUILDING_100_STREAMLIT_RULE_VALIDATION.md](docs/BUILDING_100_STREAMLIT_RULE_VALIDATION.md)
