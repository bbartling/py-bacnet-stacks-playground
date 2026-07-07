# Vibe19 build checkpoints

Ordered slices for agent/human iteration. Complete top-to-bottom unless the user scopes a single item.

---

## Done (reference implementation)

- [x] External `DATA_ROOT` via `shared/data_config.py` + `validate_data.py`
- [x] Poll interval from `manifest.json` (5-min import)
- [x] Port `csv_fdd_dashboard` (9 HTML pages, economizer FDD, sensor QA)
- [x] Flask `full` / `deploy` modes + PA packaging scripts
- [x] Scaffold `fdd_dashboard_model` (PointCatalog, VAV loader)
- [x] Agent spec + skills (`vibe19_agent_spec/`)

---

## Next for agent (ordered)

1. **VAV terminal FDD (cookbook §5)** — damper stuck, airflow tracking, reheat via `fdd_dashboard_model`; new `vav_diagnostics_page.py` + tests
2. **Building 50 parity** — `$env:HVAC_BUILDING=BUILDING_50`; fix/ignore bad `point_name` on 2 boxes; regenerate all pages
3. **Rule catalog index page** — table of implemented vs [pandas cookbook](https://bbartling.github.io/open-fdd/rules/cookbook/pandas-cookbook.html) rules with fault hours
4. **Central plant rules (cookbook §7)** — extend `central_plant.html` with CHW/HW cookbook masks
5. **Export rule to Open-FDD SQL** — optional `docs/economizer_fdd_rules.sql` pattern for new rules
6. **Multi-building index** — single hub linking B50 + B100 when `DATA_ROOT` has both
7. **CI snippet** — pytest on push (no CSV fixture; synthetic only)

---

## Per-new-building checklist

- [ ] `DATA_ROOT/{BUILDING_ID}/manifest.json` with `grid_minutes`
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
