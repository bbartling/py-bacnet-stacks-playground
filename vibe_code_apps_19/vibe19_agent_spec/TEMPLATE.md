# Make your own CSV FDD dashboard

App 19 is a **reusable template**, not a single-building product. The code in this repo is the pattern; **your CSV tree + your rules + your pages** are the deliverable.

`BUILDING_100` and `BUILDING_50` in this repo are **reference examples** used to develop and test the template. They are not shipped in git — you point at your own data.

---

## What you keep vs change

| Layer | Usually keep (template) | You customize |
| --- | --- | --- |
| Data layout | [`DATA_CONTRACT.md`](DATA_CONTRACT.md) | Your `DATA_ROOT`, building id, equipment folders |
| Validation | `validate_data.py`, `shared/data_config.py` | Fix gaps until GO |
| Rule engines | `economizer_fdd_engine.py`, `sensor_qa_engine.py` patterns | Point mappings, thresholds, which rules apply |
| Params | `dashboard_params.py` structure | Defaults, page groupings, labels |
| **Data model** | `haystack_rdf/` + `/data_model.html` | Bootstrap from CSV, SPARQL tune, JSON import/export for AI |
| Pages | `generate_dashboard.py` page pattern | Add/remove AHUs, plant, VAV pages for your site |
| UI theme | [`docs/DASHBOARD_UI_SPEC.md`](docs/DASHBOARD_UI_SPEC.md) | Title, copy, nav links, season windows |
| Deploy | `package_dashboard.py`, FastAPI `deploy` mode, Docker | Client zip, container, branding |

---

## Greenfield workflow (any site)

1. **Export CSV tree** — Open-FDD sidecar or compatible wide history (see [Open-FDD CSV import](https://bbartling.github.io/open-fdd/drivers/csv-batch-import/))
2. **Set paths** — copy `.env.example` → `.env` with `HVAC_DATA_ROOT` + `HVAC_BUILDING`, or use `data_paths.local.yaml`
3. **Validate** — `python validate_data.py` until GO
4. **Map points** — `columns.csv` `point_role` → mapping JSON for economizer / zones / plant
5. **Adjust equipment** — rename `ahu_1`/`ahu_2` pages or add pages for your AHU count; same for chillers/boilers
6. **Tune rules** — analyst panel params; add cookbook rules as needed ([pandas cookbook](https://bbartling.github.io/open-fdd/rules/cookbook/pandas-cookbook.html))
7. **Generate + serve** — `python generate_dashboard.py` (static) or `python app.py` (local tune)
8. **Deliver** — read-only zip or Docker deploy bundle for the client

---

## Generic code rules (for agents & forks)

1. **Never hardcode** a customer building name, path, AHU count, or poll interval in committed Python
2. **Read identity from config** — `get_config().building_id`, `manifest.json`, folder names under `{BUILDING}/`
3. **Example-specific notes** belong in `SESSION_LOG.md` or site operator guides — not in core engine logic
4. **Tests use synthetic fixtures** — no client CSV in git
5. **Page list is data-driven where possible** — discover `AHU_*` folders; don’t assume exactly two AHUs forever

---

## Reference example (development only)

The maintainers develop against `BUILDING_100` / `BUILDING_50` under an external `HVAC_DATA_ROOT`. Gaps and progress for that example are logged in [`SESSION_LOG.md`](SESSION_LOG.md) — treat as dev diary, not requirements for your fork.

---

## Fork checklist

- [ ] Own `DATA_ROOT` validates GO
- [ ] Package title / building label from session or manifest (not "Building 100")
- [ ] Nav matches your equipment (AHUs, plant, optional VAV page)
- [ ] Point mappings reviewed by a human analyst
- [ ] Operator guide updated for your site’s known export limitations
- [ ] Client zip tested offline (embedded Plotly, no CDN)
