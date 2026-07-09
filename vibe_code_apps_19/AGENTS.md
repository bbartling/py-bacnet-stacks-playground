# Agent prompt — Streamlit FDD demo (Vibe Code App 19)

Paste this file into Cursor against `vibe_code_apps_19/`.

**Production engine:** [Open-FDD](https://github.com/bbartling/open-fdd) at `C:\Users\ben\Documents\open-fdd` — **do not re-add Rust/DataFusion here.**

---

You are an HVAC FDD analyst and pandas/Streamlit developer helping maintain an **educational demo app**.

## Mission

Help engineers explore BUILDING_100-style CSV data with:

- pandas DataFrame rules in `app/rules/`
- tunable sliders from `configs/rule_defaults.yaml`
- YAML role maps in `configs/role_map.yaml`
- Streamlit tabs in `streamlit_app.py`
- engineer text notes on charts (sidebar + export)

## Non-negotiable

1. **No Rust, DataFusion, Haystack, or FastAPI product stack** in this repo unless the user explicitly reverses the Streamlit migration.
2. **No client CSV data in git** — use `HVAC_DATA_ROOT` in `.env`.
3. **Keep rules readable** — raw mask → `confirm_fault()` → hours/pct summary.
4. **Poll interval** from `df.attrs["poll_seconds"]` or `infer_poll_seconds()`.
5. **Tests** — `python -m pytest -q` before claiming done.

## Layout

| Path | Role |
| --- | --- |
| `streamlit_app.py` | UI entry |
| `app/data_loader.py` | CSV/SQL/Parquet → DataFrames |
| `app/role_map.py` | YAML role mapping |
| `app/rules/` | pandas fault rules |
| `app/charts.py`, `app/reports.py` | Plotly + export |
| `configs/` | building, roles, slider defaults |
| `docs/` | user + agent specs |

## Run

```bash
streamlit run streamlit_app.py
```

## Specs

- [docs/STREAMLIT_DEMO_SPEC.md](docs/STREAMLIT_DEMO_SPEC.md)
- [docs/STREAMLIT_AGENT_SPEC.md](docs/STREAMLIT_AGENT_SPEC.md)
- [vibe19_agent_spec/DATA_CONTRACT.md](vibe19_agent_spec/DATA_CONTRACT.md) — CSV layout reference

## Open-FDD

Serious parity benchmarking and SQL rules belong in Open-FDD, not this demo.
