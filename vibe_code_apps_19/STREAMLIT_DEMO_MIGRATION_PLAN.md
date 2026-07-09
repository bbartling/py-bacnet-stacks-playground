# Streamlit pandas demo — migration inventory

> Branch: `streamlit-pandas-demo-vibe19`  
> Open-FDD port verified at `C:\Users\ben\Documents\open-fdd` (`cargo test --workspace` passes).

## Remove from Vibe App 19 (after Open-FDD verification)

| Path | Reason |
| --- | --- |
| `rust_fdd_core/` | Rust/DataFusion engine — canonical copy in Open-FDD |
| `sql_rules/` | SQL rule templates — moved to Open-FDD |
| `rule_tuning/` | SQL tuning YAML for Rust registry |
| `haystack_rdf/` | Oxigraph/Haystack model — out of scope for demo |
| `fdd_app/` | FastAPI + static Plotly dashboard — replaced by Streamlit |
| `fdd_dashboard_model/` | Typed loader for old dashboard — superseded by `app/data_loader.py` |
| `.cache/parquet/`, `.cache/rule_results/` | Rust production cache assumptions |
| `Dockerfile`, `Dockerfile.deploy`, `docker-compose.yml` | Old deploy stack |
| Rust benchmark docs in `vibe19_agent_spec/benchmarks/` | Belong in Open-FDD |

## Keep / adapt

| Path | Role |
| --- | --- |
| `app/` | New Streamlit demo core |
| `configs/` | Building, roles, slider defaults |
| `tests/` | pytest for loaders, rules, smoke import |
| `docs/` | Streamlit demo guides |
| `shared/data_config.py`, `shared/env_loader.py` | Optional env helpers (may simplify later) |
| `vibe19_agent_spec/DATA_CONTRACT.md` | CSV layout reference |
| `examples/` | Small fixtures only |

## Simplify

| Was | Now |
| --- | --- |
| `AGENTS.md` (FastAPI/Rust) | Streamlit educational demo agent spec |
| `README.md` | Quick start for Streamlit + BUILDING_100 |
| `validate_data.py` | Optional — data validation via `app/data_loader.validate_dataframe` |

## New layout

```text
vibe_code_apps_19/
  streamlit_app.py
  pyproject.toml
  app/
  configs/
  tests/
  docs/
```

## Phase checklist

- [x] Open-FDD port verified
- [x] Branch `streamlit-pandas-demo-vibe19`
- [x] `app/` data loader, roles, rules, charts, reports
- [x] `streamlit_app.py` with 8 tabs + 50 rules + engineer notes + sliders
- [x] 50-rule cookbook (`cookbook_catalog.py`)
- [x] BUILDING_100 validation doc (2400 evaluations, 0 errors)
- [x] 118 pytest green
- [x] Remove Rust/SQL/FastAPI trees
- [x] Rewrite README + AGENTS.md
- [x] Manual Streamlit smoke (app launches; BUILDING_100 at `./data/hvac_systems_CLEANED`)
