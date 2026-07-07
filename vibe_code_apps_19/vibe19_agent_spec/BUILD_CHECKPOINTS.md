# Vibe19 build checkpoints

Ordered slices for agent/human iteration. Complete top-to-bottom unless the user scopes a single item.

**Product:** forkable dashboard **template** — see [`TEMPLATE.md`](TEMPLATE.md). Checkpoints below improve the template; reference-building work is labeled explicitly.

**Living doc:** agents update this file after every slice. See also [`SESSION_LOG.md`](SESSION_LOG.md).

---

## Done (reference implementation)

- [x] External `DATA_ROOT` via `shared/data_config.py` + `.env` / `env_loader.py` + `validate_data.py`
- [x] Poll interval from `manifest.json` + **auto-resample** sub-5-min data to 5-min means (`timeseries_grid.py`)
- [x] Port `csv_fdd_dashboard` (9 HTML pages + `data_model.html`, economizer FDD, sensor QA)
- [x] Flask `full` / `deploy` modes + **Docker** (`Dockerfile`, `docker-compose.yml`, `DEPLOY.md`)
- [x] Scaffold `fdd_dashboard_model` (PointCatalog, VAV loader)
- [x] Agent spec + skills (`vibe19_agent_spec/`)
- [x] **Open-Meteo economizer rules** — ECON-2, NOT_ECONOMIZING, MECH_COOLING, free-cool opp; tunable OA/dew-point limits
- [x] **Analyst workspace** — 45 rule-grouped tunables (`dashboard_params.py`), inline + rail sliders (`dashboard_tune.js`)
- [x] **Performance stack** — Feather CSV cache, filesystem path discovery, `dashboard_cache.py` (raw + context + **HTML body**), shell-first pages, prewarm, stampede protection
- [x] **Haystack RDF / SPARQL** — `haystack_rdf/`, CSV bootstrap, Flask `/api/rdf/*`, `data_model.html`
- [x] **Branding** — Open FDD Vibe Coder (`shared/branding.py`)
- [x] *(reference example)* **BUILDING_100 VAV import** — 43 per-box folders; mixed grid; validate GO

---

## Next for agent (ordered)

### Template (any site)

1. **Discover equipment from data** — auto-detect AHU pages from SPARQL / `list_equipment(haystack_tag='ahu')`; drop hardcoded `ahu_1`/`ahu_2` page ids
2. **VAV terminal FDD (cookbook §5)** — damper, airflow, reheat via `fdd_dashboard_model`; `vav_diagnostics_page.py` + tests
3. **Rule catalog index page** — table of implemented vs [pandas cookbook](https://bbartling.github.io/open-fdd/rules/cookbook/pandas-cookbook.html) rules with fault hours
4. **Central plant rules (cookbook §7)** — extend `central_plant.html` with CHW/HW cookbook masks
5. **SPARQL-driven fault scope** — rule catalog picks applicable equipment via graph queries (offline batch, not per-request)
6. **Export rule to Open-FDD SQL** — optional `docs/economizer_fdd_rules.sql` pattern for new rules
7. **Multi-building hub** — index linking all `{BUILDING_ID}` folders under `DATA_ROOT`
8. **CI snippet** — pytest on push (synthetic fixtures only; no client CSV)

### Reference example only (BUILDING_100 / 50)

9. **BUILDING_100 data gaps** — 74 VAV IDs without per-box export; 2 missing AHU zone columns; 7 orphan VAV folders
10. **Building 50 parity** — validate + regenerate; fix/ignore bad `point_name` on affected boxes

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
