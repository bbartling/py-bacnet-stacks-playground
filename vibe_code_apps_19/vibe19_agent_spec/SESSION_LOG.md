# Vibe19 session log

Rolling changelog for **reference-example development** (e.g. BUILDING_100). This is a dev diary for testing the **template** — not requirements every fork must meet.

**Append newest entries at the top.** Keep entries short — link to code, not prose dumps.

For onboarding your own site, start with [`TEMPLATE.md`](TEMPLATE.md).

---

## 2026-07-08 — Custom rule/ML lab + Flask → FastAPI migration

**Done:**
- **Custom rule plugin system** — `rules/` (Pydantic `RuleManifest`/`RuleContext`/`RuleResult`, `confirm_fault` helper, disk-based `RuleRegistry`); example plugins: `custom_sat_hunting` (pandas) + `ml_oat_residual` (sklearn IsolationForest w/ z-score fallback). Frontend rules lab (`static/dashboard_rules.js`) + `custom_rules` page.
- **Migrated Flask → FastAPI** — `app.py` is now an ASGI FastAPI app; RDF blueprint ported to `haystack_rdf/fastapi_routes.py`; deleted `flask_routes.py`. Typed request bodies in `api_models.py`; sessions via Starlette `SessionMiddleware`; `/docs` + `/openapi.json` live. Entry: `asgi.py` (Uvicorn / Gunicorn `UvicornWorker`); Dockerfiles + `requirements.txt` updated. Heavy pandas endpoints stay sync → run in threadpool; cache behavior unchanged.
- **Why FastAPI, not for speed:** API-first/forkable contract, Pydantic validation, auto OpenAPI, aligns with open-fdd bridge. See `docs/PERFORMANCE_AND_LOADING.md` (Flask vs FastAPI).
- **61 pytest green** after migration (incl. RDF routes via `fastapi.testclient`).

---

## 2026-07-08 — Dashboard mega-reorg + Arrow/plugins roadmap

**Done:**
- ECM cards, light/dark theme, engineer PIN + package lock, site occupancy settings
- `page_registry`, dynamic AHU nav, chiller/boiler split, motor runtime, analytics export
- 61 pytest green (incl. registry, occupancy, auth, rollups)
- **`docs/ROADMAP_ARROW_PLUGINS_ML.md`** — Arrow/DuckDB next steps, custom rule plugins, Pydantic boundaries, ML hooks, `HistorySource` protocol

**Next (planned):** Pydantic API schemas → `HistorySource` → DuckDB zone experiment → rule plugin registry.

---

**Done:**
- **`timeseries_grid.py`** — sub-5-min historian → 5-min means; ≥5-min unchanged; `effective_poll_seconds` on DataFrame
- **Feather cache**, fast path discovery, HTML body cache, shell-first Flask UX
- **Docker deploy** replaces PythonAnywhere (`Dockerfile`, `docker-compose.yml`, `DEPLOY.md`)
- **Agent spec revision** — AI quick rules in `vibe19_agent_spec/AGENTS.md`, updated skills, `PERFORMANCE_AND_LOADING.md`, checkpoints
- **40/40 pytest** green (timeseries, economizer, haystack, env bootstrap)

**AI agents:** start at `vibe19_agent_spec/AGENTS.md` quick rules; never SPARQL on HTTP hot path.

---

## 2026-07-07 — Haystack RDF / SPARQL data model

**Done:**
- New package `haystack_rdf/` — Haystack TTL (not Brick), rdflib SPARQL, JSON import/export
- CSV bootstrap → `data/rdf/{BUILDING}/model.json` + `data_model.ttl` (1917 points on BUILDING_100)
- Flask routes `/api/rdf/*` + `/data_model.html` (plain JS SPARQL explorer, prebuilt queries)
- `economizer_fdd_engine.resolve_columns()` — SPARQL-first with JSON fallback
- Tests: `test_haystack_rdf.py` (9 tests); **39/39 total** dashboard pytest green
- Skill: `vibe19-haystack-rdf/SKILL.md`

**Try:** http://127.0.0.1:5000/data_model.html → Bootstrap from CSV

**Next:** dynamic AHU pages from SPARQL equipment discovery; SPARQL fault scope

---

## 2026-07-07 — Template intent documented

**Product framing:** App 19 is a forkable dashboard template; BUILDING_100/50 are reference examples only. Added [`TEMPLATE.md`](TEMPLATE.md), template-first principle in `AGENTS.md`, reordered `BUILD_CHECKPOINTS.md` (template vs reference-example work).

---

## 2026-07-07 — Performance + Open-Meteo economizer tuning *(reference example: BUILDING_100)*

**Building:** `BUILDING_100` · data via `HVAC_DATA_ROOT` (external, not in git)

**Done:**
- Open-Meteo economizer OK logic in `economizer_fdd_engine.py` (DP &lt; 60°F, OAT band, min OA ~20%, full econ ~95%)
- Revised ECON-2, NOT_ECONOMIZING, MECH_COOLING; free-cool opportunity / econ2 / econ3 faults in `generate_dashboard.py`
- New charts: OAT vs SAT scatter, CHWS vs OAT, HWS vs OAT, duct static violin; ECM5 chiller-only fix
- Analyst tunables: `economizer_low_limit_f`, `oa_min_expected_pct`, `oa_max_economizer_pct`, dew point on more pages
- **`dashboard_cache.py`** — param-keyed context cache, CSV mtime invalidation, per-page lazy `compute_context(page_id=...)`, background prewarm, economizer diagnostics HTML skip
- **`app.py`** wired to cache; AHU pages ~0.15s compute vs ~8s full pipeline
- BUILDING_100: 43 VAV per-box folders merged; mixed grid in manifest (AHU/weather 15-min, VAV 5-min); `validate_data.py` → GO

**Tests:** 30/30 (`test_economizer_diagnostics.py`, `test_sensor_qa.py`)

**Known gaps (BUILDING_100):**
- 74 mapped VAV IDs still lack per-box CSV folders (space temp only in AHU wide)
- 7 VAV folders not in `vav_to_ahu_simple.csv`
- 2 AHU zone columns missing from `history_wide.csv`
- `BUILDING_50` not refreshed

**Next:** VAV terminal FDD (cookbook §5) · Building 50 parity · rule catalog index page
