# Vibe19 agent workspace — orientation

Plain Markdown on disk is the source of truth for **Cursor**, **Codex CLI**, and **OpenClaw**-style agents. Product code lives in `vibe_code_apps_19/`; orchestration lives in **`vibe19_agent_spec/`**.

**Primary agent prompt (paste into new sessions):** [`../AGENTS.md`](../AGENTS.md)

**Make your own (product intent):** [`TEMPLATE.md`](TEMPLATE.md) — forkable template; `BUILDING_100` / `BUILDING_50` are reference examples only.

**App title (UI):** **Open FDD Vibe Coder** — see `shared/branding.py`.

---

## AI agent quick rules (read first)

1. **Never commit client CSV history** — use `HVAC_DATA_ROOT` / `.env` (see `.env.example`).
2. **Load historian data through `read_history_csv`** or apply `maybe_downsample_to_5min` — sub-5-min data → 5-min means; ≥5-min unchanged.
3. **Use `df.attrs["effective_poll_seconds"]`** for `confirm_fault` rollups when available — do not hardcode 900 unless data is 15-min.
4. **Never call SPARQL on the HTTP hot path** for path discovery — use filesystem CSV discovery + caches (see [`docs/PERFORMANCE_AND_LOADING.md`](docs/PERFORMANCE_AND_LOADING.md)).
5. **FastAPI full mode is shell-first** — pages load instantly; charts arrive via `POST /api/refresh/<page_id>`. Heavy endpoints stay sync (`def`) so pandas runs in the threadpool.
6. **Compute lazily per page** — pass `page_id` to `compute_context()`; use `dashboard_cache`.
7. **Rules follow Open-FDD pandas cookbook** — raw mask → optional smooth → `confirm_fault()` → rollup hours.
8. **Equipment identity** — `point_role` + folder path > vendor `point_name`.
9. **Deploy = Docker or static zip** — not PythonAnywhere; see `csv_fdd_dashboard/DEPLOY.md`.
10. **Update this spec after meaningful changes** — `BUILD_CHECKPOINTS.md`, `SESSION_LOG.md`, relevant skill.
11. **Custom rules = disk plugins only** — never `exec()` Python from API; see [`docs/ROADMAP_ARROW_PLUGINS_ML.md`](docs/ROADMAP_ARROW_PLUGINS_ML.md).

---

## Bootstrap order (each agent wake)

1. **`../AGENTS.md`** — mission, non-negotiables, repo map
2. **AI quick rules above** — performance + data-loading pitfalls
3. **`BUILD_CHECKPOINTS.md`** — pick **one** slice from “Next for agent (ordered)”
4. **`SESSION_LOG.md`** — skim latest entry
5. **`DATA_CONTRACT.md`** — if touching imports, pandas load, or new building
6. **`docs/PERFORMANCE_AND_LOADING.md`** — if touching cache, Feather, resampling, or FastAPI refresh
7. **`skills/<topic>/SKILL.md`** — when checkpoint names a topic
8. **`docs/DASHBOARD_UI_SPEC.md`** — if adding/changing HTML pages
9. **`docs/OPENFDD_PARITY.md`** — if adding FDD rules

Do **not** paste entire Open-FDD doc sites into prompts — link and implement the specific rule section.

---

## Spec maintenance (every session)

**Keep this tree current as you code.** The user expects the spec to track reality without a separate ask.

After each meaningful slice:

1. **`BUILD_CHECKPOINTS.md`** — move completed items to Done; adjust Next order if priorities shifted
2. **`SESSION_LOG.md`** — append a dated entry (what changed, tests run, known gaps)
3. **Relevant skill or doc** — e.g. FastAPI UI → `skills/vibe19-flask-analyst-ui/SKILL.md`; load path → `PERFORMANCE_AND_LOADING.md`
4. **`../AGENTS.md`** — only if repo map, commands, or non-negotiables changed

Do **not** commit client CSV paths or secrets into the spec.

---

## Human vs agent roles

| Responsibility | Human | Agent |
| --- | --- | --- |
| Client CSV export / Open-FDD import | Provides `DATA_ROOT` path | Validates layout, documents gaps |
| Point mapping sign-off | Approves `point_role` → column maps | Drafts mapping JSON from `columns.csv` |
| Fault thresholds | Tunes with analyst panel (45 rule params) | Exposes params in `dashboard_params.py` |
| Client delivery | Runs Docker / uploads Drive zip | Builds `package_dashboard.py` / `build_docker_deploy.py` |
| BACnet / live writes | Field work | **Out of scope** for App 19 |

---

## Repository map

| Path | Role |
| --- | --- |
| `shared/` | `data_config`, `env_loader`, `validate_hvac_data`, `branding` |
| `haystack_rdf/` | Feather cache, grid resample, RDF/SPARQL, CSV bootstrap |
| `csv_fdd_dashboard/` | Plotly HTML + FastAPI + `dashboard_cache.py` |
| `fdd_dashboard_model/` | Enhanced catalogs + VAV loaders (terminal rules) |
| `Dockerfile`, `docker-compose.yml` | Container deploy (analyst + deploy modes) |
| `data/` | Pointer / junction docs — no bulk CSV in git |
| `vibe19_agent_spec/` | This tree |

---

## Skill index

| Skill | When |
| --- | --- |
| `skills/vibe19-hvac-data-import/` | New site CSV tree, manifest, `.env`, validation |
| `skills/vibe19-pandas-fdd-rules/` | Cookbook rule → pandas engine, poll/grid |
| `skills/vibe19-haystack-rdf/` | RDF model, SPARQL UI, resolver, bootstrap |
| `skills/vibe19-plotly-dashboard/` | HTML pages, Plotly figures, seasons |
| `skills/vibe19-flask-analyst-ui/` | FastAPI tune sliders, shell-first refresh, rules lab, deploy mode |
| `skills/vibe19-deploy-packaging/` | Client zip, Docker, sanitized export |
| `skills/vibe19-point-catalog/` | VAV/AHU model, terminal faults |

Cursor users: mirror skills under repo `.cursor/skills/` if desired; **`vibe19_agent_spec/skills/`** is canonical.

---

## Reference example sites (development only)

| Key | Value |
| --- | --- |
| Data root | `HVAC_DATA_ROOT` in `.env` or `data_paths.local.yaml` |
| Example buildings | `BUILDING_100`, `BUILDING_50` |
| Grid | `manifest.json` `grid_minutes`; **auto-resample** if actual Δt &lt; 5 min |
| VAV | Per-box folders under `{BUILDING}/VAV/{id}/` when exported |
| Session log | [`SESSION_LOG.md`](SESSION_LOG.md) |

Never hardcode customer-specific paths or building labels in committed code.

---

## Smoke scripts (before claiming done)

```bash
cd vibe_code_apps_19
python validate_data.py

cd csv_fdd_dashboard
pip install -r requirements-dev.txt
python -m pytest test_timeseries_grid.py test_economizer_diagnostics.py test_haystack_rdf.py test_csv_env_bootstrap.py -q
python app.py   # → http://127.0.0.1:5000/index.html (shell ~0.05s; charts via refresh)
```

After each task: update **`BUILD_CHECKPOINTS.md`** and append **`SESSION_LOG.md`** when non-trivial.
