# Vibe19 build checkpoints

Ordered slices for agent/human iteration. Complete top-to-bottom unless the user scopes a single item.

**Product:** forkable dashboard **template** — see [`TEMPLATE.md`](TEMPLATE.md). Checkpoints below improve the template; reference-building work is labeled explicitly.

**Living doc:** agents update this file after every slice. See also [`SESSION_LOG.md`](SESSION_LOG.md).

---

## Done (reference implementation)

- [x] External `DATA_ROOT` via `shared/data_config.py` + `.env` / `env_loader.py` + `validate_data.py`
- [x] Poll interval from `manifest.json` + **auto-resample** sub-5-min data to 5-min means (`timeseries_grid.py`)
- [x] Port `fdd_app` (9 HTML pages + `data_model.html`, economizer FDD, sensor QA)
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
- [x] Renamed `csv_fdd_dashboard/` → **`fdd_app/`** with `backend/`, `frontend/static/`, `sidecar/` split. Removed dead code (`wsgi.py`, `dashboard_server.py`, `pandas_rule_scaffolds`). Deleted committed generated HTML/CSV artifacts.
- [x] **Rust FDD core stage 1** — `rust_fdd_core/` workspace (7 crates), `sql_rules/` (8 rules), `fdd_cli` validate/ingest/query/benchmark, Parquet sidecars, docs + benchmark report. Python dashboard unchanged (102 pytest green).
- [x] **Rust FDD core stage 2 (parity + wiring)** — pandas oracle export, hardened compare + markdown report, poll interval `{{POLL_SECONDS}}`, 19 SQL rules, role mapping doc, `VIBE19_RUST_CACHE=1` warmup. BUILDING_100: 229 metric pass / 49 fail (analytics proven; fault confirm/proxy gaps documented). 103 pytest green.
- [x] **Stage 4 branch reconciliation** — audit clean; `develop` only; `stage4-finish-parity-and-tuning` created; baseline 314/54 confirmed. See `BRANCH_RECONCILIATION_STAGE4.md`.

---

## Next for agent (ordered)

### Stage 4 parity (on `stage4-finish-parity-and-tuning`)

1. **OAT-METEO** — timestamp join audit vs Python weather merge (P0)
2. **ECON-4** — fan gate + OA fraction + confirm sample dumps (P0)
3. **FC8/FC13/FC10/FC2/FC9/FC12** — threshold + confirm fixtures (P1)
4. **VAV-1** — 34 small confirm residuals (P2)
5. **Complete registry `parameters:`** for all 19 rules

### Template (any site)

1. ~~**Pydantic API schemas**~~ ✅ done — typed bodies in `fdd_app/backend/api_models.py` (validated by FastAPI on `/api/login`, `/api/config`, `/api/refresh`, `/api/rules/run`)
2. **`HistorySource` protocol** — abstract CSV loader; stub `SqlHistorySource` for DuckDB/pg
3. ~~**DuckDB zone rollups**~~ ✅ done — `duckdb_rollups.py` (zone comfort %, OAT bins, weekly means); wired into `compute_mech_cool_oat_bins`; pandas fallback + tests
4. ~~**Custom rule plugins**~~ ✅ done — `rules/plugins/` + `RuleRegistry` + pandas & sklearn examples + tests pending expansion
5. **Tests for rule registry + plugins** — cover discovery, param validation, `confirm_fault`, ML fallback
6. **VAV terminal FDD (cookbook §5)** — damper, airflow, reheat via `fdd_dashboard_model`; `vav_diagnostics_page.py` + tests
7. **Rule catalog index page** — implemented vs cookbook rules with fault hours
8. ~~**Parquet sidecar option**~~ ✅ done — `feather_cache.read_history_parquet()` with column pruning; same mtime invalidation
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
