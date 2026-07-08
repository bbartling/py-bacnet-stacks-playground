# Vibe19 build checkpoints

Ordered slices for agent/human iteration. Complete top-to-bottom unless the user scopes a single item.

**Product:** forkable dashboard **template** — see [`TEMPLATE.md`](TEMPLATE.md). Checkpoints below improve the template; reference-building work is labeled explicitly.

**Living doc:** agents update this file after every slice. See also [`SESSION_LOG.md`](SESSION_LOG.md).

---

## Done (reference implementation)

- [x] External `DATA_ROOT` via `shared/data_config.py` + `.env` / `env_loader.py` + `validate_data.py`
- [x] Poll interval from `manifest.json` + **auto-resample** sub-5-min data to 5-min means (`timeseries_grid.py`)
- [x] Port `csv_fdd_dashboard` (9 HTML pages + `data_model.html`, economizer FDD, sensor QA)
- [x] **FastAPI** `full` / `deploy` modes (migrated from Flask; `asgi.py`, `/docs`, `api_models.py`) + **Docker** (`Dockerfile`, `docker-compose.yml`, `DEPLOY.md`)
- [x] **Custom rule/ML plugin lab** — `rules/` registry + Pydantic manifests, pandas + sklearn example plugins, `/api/rules[/run]`, rules-lab UI
- [x] Scaffold `fdd_dashboard_model` (PointCatalog, VAV loader)
- [x] Agent spec + skills (`vibe19_agent_spec/`)
- [x] **Open-Meteo economizer rules** — ECON-2, NOT_ECONOMIZING, MECH_COOLING, free-cool opp; tunable OA/dew-point limits
- [x] **Analyst workspace** — 45 rule-grouped tunables (`dashboard_params.py`), inline + rail sliders (`dashboard_tune.js`)
- [x] **Performance stack** — Feather CSV cache, filesystem path discovery, `dashboard_cache.py` (raw + context + **HTML body**), shell-first pages, prewarm, stampede protection
- [x] **Dashboard mega-reorg** — ECM cards, theme toggle, SPARQL nav (`page_registry`), engineer PIN + package lock, site settings/occupancy, plant split, motor runtime, analytics export
- [x] **Haystack RDF / SPARQL** — `haystack_rdf/`, CSV bootstrap, FastAPI `/api/rdf/*` (`fastapi_routes.py`), `data_model.html`
- [x] **Branding** — Open FDD Vibe Coder (`shared/branding.py`)
- [x] *(reference example)* **BUILDING_100 VAV import** — 43 per-box folders; mixed grid; validate GO

---

## Next for agent (ordered)

### Template (any site)

1. ~~**Pydantic API schemas**~~ ✅ done — typed bodies in `csv_fdd_dashboard/api_models.py` (validated by FastAPI on `/api/login`, `/api/config`, `/api/refresh`, `/api/rules/run`)
2. **`HistorySource` protocol** — abstract CSV loader; stub `SqlHistorySource` for DuckDB/pg
3. **DuckDB zone rollups** — experiment on `zones` page vs pandas groupby
4. ~~**Custom rule plugins**~~ ✅ done — `rules/plugins/` + `RuleRegistry` + pandas & sklearn examples + tests pending expansion
5. **Tests for rule registry + plugins** — cover discovery, param validation, `confirm_fault`, ML fallback
6. **VAV terminal FDD (cookbook §5)** — damper, airflow, reheat via `fdd_dashboard_model`; `vav_diagnostics_page.py` + tests
7. **Rule catalog index page** — implemented vs cookbook rules with fault hours
8. **Parquet sidecar option** — optional format in `feather_cache`
9. **ML plugin example** — ⏳ started (`rules/plugins/ml_oat_residual.py`); next: offline-trained joblib artifact + `models/` convention + parity test
10. **Multi-building hub** — index linking all `{BUILDING_ID}` folders under `DATA_ROOT`
11. **CI snippet** — pytest on push (synthetic fixtures only; no client CSV)

### Reference example only (BUILDING_100 / 50)

12. **BUILDING_100 data gaps** — 74 VAV IDs without per-box export; 2 missing AHU zone columns; 7 orphan VAV folders
13. **Building 50 parity** — validate + regenerate; fix/ignore bad `point_name` on affected boxes

---

## Per-new-building checklist

- [ ] `.env` or `data_paths.local.yaml` with `HVAC_DATA_ROOT` + `HVAC_BUILDING`
- [ ] `DATA_ROOT/{BUILDING_ID}/manifest.json` with `grid_minutes` and `timezone`
- [ ] `weather/history_wide.csv` row count ≈ AHU history (after resampling if needed)
- [ ] `columns.csv` + `history_wide.csv` per AHU
- [ ] Optional `VAV/{id}/` per terminal
- [ ] `python validate_data.py` → GO
- [ ] Haystack bootstrap: `/data_model.html` or `POST /api/rdf/bootstrap`
- [ ] Point mapping JSON for economizer + zones
- [ ] Generate + spot-check index + one AHU page (Flask refresh &lt; 1s warm)
- [ ] Client package or Docker deploy image if delivering

---

## Non-goals (App 19)

- Live BACnet / Haystack polling (see App 12 / Open-FDD edge)
- Committing client CSV history to git
- Replacing Open-FDD SQL engine — parity only, offline pandas twin
- Migrating to FastAPI solely for “async” — pandas compute is CPU-bound; cache first
