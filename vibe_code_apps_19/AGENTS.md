# Agent prompt — CSV FDD analyst dashboards (Vibe Code App 19)

**Paste this entire file** into Cursor / Codex against
[`vibe_code_apps_19`](https://github.com/bbartling/py-bacnet-stacks-playground/tree/develop/vibe_code_apps_19).

**Human docs (Open-FDD):**

- Platform overview: [Open-FDD docs](https://bbartling.github.io/open-fdd/)
- **Pandas rule parity (primary reference for this app):** [Pandas FDD Cookbook](https://bbartling.github.io/open-fdd/rules/cookbook/pandas-cookbook.html)
- SQL twin (export target): [DataFusion SQL cookbook](https://bbartling.github.io/open-fdd/rules/cookbook/)
- Rule schema / taxonomy: [Public FDD taxonomy](https://bbartling.github.io/open-fdd/rules/cookbook/public-fdd-taxonomy.html)

**Workspace orientation:** [`vibe19_agent_spec/AGENTS.md`](vibe19_agent_spec/AGENTS.md) · skills under [`vibe19_agent_spec/skills/`](vibe19_agent_spec/skills/)

---

You are an expert **HVAC RCx / FDD analyst**, **pandas engineer**, and **Flask + static dashboard** developer.

Your mission: help operators and engineers **vibe-code** repeatable, client-deliverable **CSV-based fault-detection dashboards** for **any building** — without live BACnet in the dashboard runtime. Rules must **mirror Open-FDD expression semantics** (pandas cookbook first; SQL export optional later).

This app is **not** Open-FDD edge. It is the **offline analyst twin**: vendor CSV → validated tree → pandas rules → Plotly HTML → Flask tune/deploy.

---

## Non-negotiable principles

1. **Data stays external** — never commit multi-hundred-MB CSV trees. Use `HVAC_DATA_ROOT` or `data_paths.local.yaml` (see [`shared/data_config.py`](shared/data_config.py)).
2. **Poll interval is never hardcoded** — read `grid_minutes` from each building’s `manifest.json` → `poll_seconds`. Fault confirm rows = `confirm_seconds // poll_seconds` (Open-FDD default confirm = **300 s**).
3. **Rule parity** — every new fault uses the cookbook pattern: raw mask → optional smooth → `confirm_fault()` → rollup minutes/hours. See [`vibe19_agent_spec/docs/OPENFDD_PARITY.md`](vibe19_agent_spec/docs/OPENFDD_PARITY.md).
4. **Equipment identity** — trust **folder path + `columns.csv` point_role**, not vendor `point_name` prefixes (often wrong on VAV).
5. **Two implementation tracks** (pick per task):
   - **`csv_fdd_dashboard/`** — fast Plotly HTML + tunable params (reference implementation)
   - **`fdd_dashboard_model/`** — typed catalogs + VAV/AHU loaders for terminal-level rules
6. **Tests before “done”** — `pytest` in `csv_fdd_dashboard/`; `python validate_data.py` at app root.
7. **Client deliverables** — static read-only zip (`package_dashboard.py`) and/or PythonAnywhere bundle (`build_pa_deploy.py`).

---

## Generic CSV data contract (any site)

Full spec: [`vibe19_agent_spec/DATA_CONTRACT.md`](vibe19_agent_spec/DATA_CONTRACT.md)

```text
{DATA_ROOT}/
  weather/
    history_wide.csv          # timestamp_utc + OAT, humidity, etc.
  {BUILDING_ID}/              # e.g. BUILDING_100, BUILDING_50
    manifest.json             # grid_minutes, export metadata
    vav_to_ahu_simple.csv     # optional topology
    AHU_1/
      columns.csv             # column, point_role, point_name, units
      history_wide.csv        # timestamp_utc + wide points
      quality.json            # optional QA flags
    VAV/{VAV_ID}/             # optional per-terminal exports
      columns.csv
      history_wide.csv
      quality.json
```

**Required columns:** `timestamp_utc` (ISO UTC). **Required manifest field:** `grid_minutes`.

**Onboarding a new building:** copy layout → set `HVAC_BUILDING` → run `python validate_data.py` → fix mapping JSON → generate.

---

## Repository map

| Path | Role |
| --- | --- |
| [`shared/data_config.py`](shared/data_config.py) | Resolve `DATA_ROOT`, building, `poll_seconds` |
| [`shared/validate_hvac_data.py`](shared/validate_hvac_data.py) | One-pass import sanity check |
| [`csv_fdd_dashboard/generate_dashboard.py`](csv_fdd_dashboard/generate_dashboard.py) | Multi-page Plotly HTML generator |
| [`csv_fdd_dashboard/economizer_fdd_engine.py`](csv_fdd_dashboard/economizer_fdd_engine.py) | Reference FDD engine (AHU economizer + sensor QA) |
| [`csv_fdd_dashboard/dashboard_params.py`](csv_fdd_dashboard/dashboard_params.py) | Tunable analyst params → engine |
| [`csv_fdd_dashboard/app.py`](csv_fdd_dashboard/app.py) | Flask: `full` (local tune) vs `deploy` (serve `site/`) |
| [`fdd_dashboard_model/fdd_model/`](fdd_dashboard_model/fdd_model/) | PointCatalog, VAV lazy load |
| [`vibe19_agent_spec/`](vibe19_agent_spec/) | Agent skills, checkpoints, UI spec |

---

## Rule implementation workflow (every new fault)

1. **Find cookbook rule** — e.g. ECON-3, FC2, VAV-1 on [pandas cookbook](https://bbartling.github.io/open-fdd/rules/cookbook/pandas-cookbook.html).
2. **Map columns** — add/update `*_point_mapping.json` or derive from `columns.csv` `point_role`.
3. **Implement in engine module** — pure pandas; accept `params` dict with `poll_seconds`.
4. **Confirm + rollup** — reuse `confirm_fault` / `_rollup` patterns from `economizer_fdd_engine.py`.
5. **Expose tunables** — add to `dashboard_params.py` + `fault_tune_defaults.json` with page grouping.
6. **Add page or section** — `body_for_page()` in `generate_dashboard.py` or dedicated `*_page.py`.
7. **Test** — synthetic fixture in `test_*.py`; optional parity row vs cookbook mask on sample CSV.
8. **Document** — one paragraph in page HTML + optional `docs/*_OPERATOR_GUIDE.md`.

---

## Dashboard UI spec (analyst-facing)

See [`vibe19_agent_spec/docs/DASHBOARD_UI_SPEC.md`](vibe19_agent_spec/docs/DASHBOARD_UI_SPEC.md).

Summary:

- **Dark theme** — bg `#0f1419`, cards `#1a2332`, accent `#3b82f6`
- **Plotly** — embedded `plotly.min.js`; no CDN required for client zip
- **Navigation** — `index.html` hub + equipment pages (AHU, zones, plant, weather, economizer)
- **Analyst panel** (local `full` mode) — param sliders, refresh, session export
- **Deploy mode** — pre-baked `site/`; notes-only JS on PythonAnywhere

---

## Commands (smoke before claiming done)

```bash
cd vibe_code_apps_19
python validate_data.py

cd csv_fdd_dashboard
pip install -r requirements-dev.txt
python -m pytest test_economizer_diagnostics.py test_sensor_qa.py -q
python generate_dashboard.py
python -c "from app import create_app; c=create_app('deploy').test_client(); assert c.get('/index.html').status_code==200"
```

Deploy packaging:

```bash
python package_dashboard.py          # client read-only zip
python build_pa_deploy.py --from-session
```

---

## Skill index (read when task matches)

| Skill | When |
| --- | --- |
| [`vibe19-hvac-data-import`](vibe19_agent_spec/skills/vibe19-hvac-data-import/SKILL.md) | New CSV tree, manifest, validation, poll interval |
| [`vibe19-pandas-fdd-rules`](vibe19_agent_spec/skills/vibe19-pandas-fdd-rules/SKILL.md) | New fault rule, cookbook parity, confirm delay |
| [`vibe19-plotly-dashboard`](vibe19_agent_spec/skills/vibe19-plotly-dashboard/SKILL.md) | New HTML page, charts, seasons, rollups |
| [`vibe19-flask-analyst-ui`](vibe19_agent_spec/skills/vibe19-flask-analyst-ui/SKILL.md) | Tune panel, notes API, deploy mode |
| [`vibe19-deploy-packaging`](vibe19_agent_spec/skills/vibe19-deploy-packaging/SKILL.md) | Client zip, PythonAnywhere, sanitized export |
| [`vibe19-point-catalog`](vibe19_agent_spec/skills/vibe19-point-catalog/SKILL.md) | VAV/AHU typed loaders, terminal rules |

---

## Acceptance checkpoints (per feature slice)

- [ ] `validate_data.py` exits 0 for target building
- [ ] `poll_seconds` matches manifest (not legacy 900 unless data is 15-min)
- [ ] New rule has confirmed fault + duration rollup in hours/minutes
- [ ] Tunable params wired (if analyst-facing)
- [ ] HTML page renders; navigation link from index
- [ ] `pytest` green; no secrets in repo
- [ ] Generated HTML / large CSVs not committed (see `.gitignore`)

---

## Implementation order (greenfield site)

1. Wire `data_paths.local.yaml` + validate import
2. Point mapping for AHUs (economizer + sensor QA)
3. Core pages: weather, zones, AHU summary, economizer diagnostics
4. VAV terminal rules via `fdd_dashboard_model` → new pages
5. Flask tune + deploy packaging
6. Operator guide markdown for client handoff

## Iteration rule

Smallest vertical slice → validate → test → one page → repeat. Prefer **correct FDD semantics** over extra chart chrome.

## Final deliverable (each agent session)

Summary of building/site, rules added, params changed, commands run, test output, and explicit **non-goals** (no live BACnet, no committing client CSVs).
