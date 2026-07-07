# Vibe19 build checkpoints

Ordered slices for agent/human iteration. Complete top-to-bottom unless the user scopes a single item.

**Product:** forkable dashboard **template** — see [`TEMPLATE.md`](TEMPLATE.md). Checkpoints below improve the template; reference-building work is labeled explicitly.

**Living doc:** agents update this file after every slice. See also [`SESSION_LOG.md`](SESSION_LOG.md).

---

## Done (reference implementation)

- [x] External `DATA_ROOT` via `shared/data_config.py` + `validate_data.py`
- [x] Poll interval from `manifest.json` (supports mixed grid — e.g. AHU 15-min + VAV 5-min)
- [x] Port `csv_fdd_dashboard` (9 HTML pages, economizer FDD, sensor QA)
- [x] Flask `full` / `deploy` modes + PA packaging scripts
- [x] Scaffold `fdd_dashboard_model` (PointCatalog, VAV loader)
- [x] Agent spec + skills (`vibe19_agent_spec/`)
- [x] **Open-Meteo economizer rules** — ECON-2, NOT_ECONOMIZING, MECH_COOLING, free-cool opp; tunable OA/dew-point limits
- [x] **Analyst performance** — `dashboard_cache.py`, per-page lazy compute, CSV mtime cache, Flask prewarm
- [x] **Template docs** — `TEMPLATE.md`, template-first principle in `AGENTS.md`
- [x] *(reference example)* **BUILDING_100 VAV import** — 43 per-box folders; mixed grid; validate GO
- [x] **Haystack RDF / SPARQL** — `haystack_rdf/` package, CSV bootstrap, Flask `/api/rdf/*`, `data_model.html` UI

---

## Next for agent (ordered)

### Template (any site)

1. **Discover equipment from data** — auto-detect `AHU_*` pages from SPARQL `list_equipment(haystack_tag='ahu')`
2. **SPARQL-driven fault scope** — rule catalog picks applicable equipment via graph queries
2. **VAV terminal FDD (cookbook §5)** — damper stuck, airflow tracking, reheat via `fdd_dashboard_model`; new `vav_diagnostics_page.py` + tests
3. **Rule catalog index page** — table of implemented vs [pandas cookbook](https://bbartling.github.io/open-fdd/rules/cookbook/pandas-cookbook.html) rules with fault hours
4. **Central plant rules (cookbook §7)** — extend `central_plant.html` with CHW/HW cookbook masks
5. **Plotly HTML cache** — optional second-level cache for rendered page bodies (compute already cached)
6. **Export rule to Open-FDD SQL** — optional `docs/economizer_fdd_rules.sql` pattern for new rules
7. **Multi-building hub** — index linking all `{BUILDING_ID}` folders found under `DATA_ROOT`
8. **CI snippet** — pytest on push (no CSV fixture; synthetic only)

### Reference example only (BUILDING_100 / 50)

9. **BUILDING_100 data gaps** — 74 VAV IDs without per-box export; 2 missing AHU zone columns; reconcile 7 orphan VAV folders
10. **Building 50 parity** — validate + regenerate; fix/ignore bad `point_name` on affected boxes

---

## Per-new-building checklist

- [ ] `DATA_ROOT/{BUILDING_ID}/manifest.json` with `grid_minutes` (note mixed grid if AHU ≠ VAV poll)
- [ ] `weather/history_wide.csv` row count ≈ AHU history
- [ ] `columns.csv` + `history_wide.csv` per AHU
- [ ] Optional `VAV/{id}/` per terminal
- [ ] `python validate_data.py` → GO
- [ ] Point mapping JSON for economizer + zones
- [ ] Generate + spot-check index + one AHU page
- [ ] Client package if delivering

---

## Non-goals (App 19)

- Live BACnet / Haystack polling (see App 12 / Open-FDD edge)
- Committing client CSV history to git
- Replacing Open-FDD SQL engine — parity only, offline pandas twin
