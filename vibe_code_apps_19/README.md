# Vibe Code App 19 — Streamlit FDD demo

Lightweight **Python + Streamlit + pandas** educational app for fault detection on BUILDING_100-style CSV historian data.

**This is not Open-FDD.** For the production Rust/DataFusion engine, see [Open-FDD](https://github.com/bbartling/open-fdd) (`C:\Users\ben\Documents\open-fdd`).

## What this app is

- Streamlit UI with tunable sliders and engineer notes
- Readable pandas fault rules (VAV comfort, SAT high, economizer, fan runtime, …)
- CSV tree, upload, local folder, read-only SQLite/DuckDB, optional Parquet
- Simple YAML role mapping — no Haystack/Oxigraph

## What this app is not

- Not a FastAPI production dashboard
- Not Rust or DataFusion
- Not a Parquet production pipeline (Parquet read is optional convenience only)

## Quick start

```powershell
cd vibe_code_apps_19
python -m pip install -e ".[dev]"
copy .env.example .env   # if present; set HVAC_DATA_ROOT
streamlit run streamlit_app.py
```

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `HVAC_DATA_ROOT` | `./data/hvac_systems_CLEANED` | Root folder with `BUILDING_100/` and `weather/` |
| `HVAC_BUILDING` | `BUILDING_100` | Building folder name |
| `HVAC_WEATHER_SUBDIR` | `weather` | Weather CSV subfolder |

## BUILDING_100

Point `HVAC_DATA_ROOT` at your local cleaned CSV tree. The app loads `manifest.json`, equipment `history_wide.csv` + `columns.csv`, and optional weather.

See [docs/CSV_INPUT_GUIDE.md](docs/CSV_INPUT_GUIDE.md).

## Upload CSV / SQL

- **Upload CSV** — sidebar file picker, then map roles
- **SQLite / DuckDB** — read-only SELECT only — [docs/SQL_INPUT_GUIDE.md](docs/SQL_INPUT_GUIDE.md)

## Role mapping

Edit `configs/role_map.yaml` or use the **Role Mapping** tab. Semantic roles (`sat`, `zone_t`, `oa_t`, …) map to CSV column names.

## Rule tuning

Sliders come from `configs/rule_defaults.yaml`. See [docs/RULE_TUNING_GUIDE.md](docs/RULE_TUNING_GUIDE.md).

## Export

**Export** tab: summary CSV, debug CSV, Markdown/HTML report (includes engineer notes).

## Tests

```powershell
python -m pytest -q
```

## Docs

- [STREAMLIT_DEMO_SPEC.md](docs/STREAMLIT_DEMO_SPEC.md)
- [STREAMLIT_AGENT_SPEC.md](docs/STREAMLIT_AGENT_SPEC.md)
- [STREAMLIT_DEMO_MIGRATION_PLAN.md](STREAMLIT_DEMO_MIGRATION_PLAN.md)

## Agent prompt

See [AGENTS.md](AGENTS.md) for Cursor/Codex instructions.
