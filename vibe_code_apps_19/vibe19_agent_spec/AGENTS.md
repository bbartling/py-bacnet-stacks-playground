# Vibe19 agent workspace — orientation

Plain Markdown on disk is the source of truth for **Cursor**, **Codex CLI**, and **OpenClaw**-style agents. Product code lives in `vibe_code_apps_19/`; orchestration lives in **`vibe19_agent_spec/`**.

**Primary agent prompt (paste into new sessions):** [`../AGENTS.md`](../AGENTS.md)

**Make your own (product intent):** [`TEMPLATE.md`](TEMPLATE.md) — this repo is a forkable template; reference buildings are examples only.

**External references:**

- [Open-FDD](https://bbartling.github.io/open-fdd/) — platform docs, CSV import, SQL rules
- [Pandas FDD Cookbook](https://bbartling.github.io/open-fdd/rules/cookbook/pandas-cookbook.html) — **source of truth for rule expressions in this app**

---

## Bootstrap order (each agent wake)

1. **`../AGENTS.md`** — mission, non-negotiables, repo map
2. **`TEMPLATE.md`** — fork/customize workflow (read when onboarding a new site)
3. **`BUILD_CHECKPOINTS.md`** — pick **one** slice from “Next for agent (ordered)”
4. **`SESSION_LOG.md`** — skim latest entry (reference-example dev diary)
5. **`DATA_CONTRACT.md`** — if touching imports or new building
6. **`skills/<topic>/SKILL.md`** — when checkpoint names a topic
7. **`docs/PERFORMANCE_AND_LOADING.md`** — if touching data load, cache, Feather, or grid resampling
8. **`docs/DASHBOARD_UI_SPEC.md`** — if adding/changing HTML pages
9. **`docs/OPENFDD_PARITY.md`** — if adding FDD rules

Do **not** paste entire Open-FDD doc sites into prompts — link and implement the specific rule section.

---

## Spec maintenance (every session)

**Keep this tree current as you code.** The user expects the spec to track reality without a separate ask.

After each meaningful slice:

1. **`BUILD_CHECKPOINTS.md`** — move completed items to Done; adjust Next order if priorities shifted
2. **`SESSION_LOG.md`** — append a dated entry (what changed, tests run, known gaps)
3. **Relevant skill or doc** — e.g. Flask work → `skills/vibe19-flask-analyst-ui/SKILL.md`; new rule → `docs/OPENFDD_PARITY.md` rule table
4. **`../AGENTS.md`** — only if repo map, commands, or non-negotiables changed

Do **not** commit client CSV paths or secrets into the spec.

---

## Human vs agent roles

| Responsibility | Human | Agent |
| --- | --- | --- |
| Client CSV export / Open-FDD import | Provides `DATA_ROOT` path | Validates layout, documents gaps |
| Point mapping sign-off | Approves `point_role` → column maps | Drafts mapping JSON from `columns.csv` |
| Fault thresholds | Tunes with analyst panel | Exposes params in `dashboard_params.py` |
| Client delivery | Uploads Docker image / Drive | Builds `package_dashboard.py` / `build_docker_deploy.py` |
| BACnet / live writes | Field work | **Out of scope** for App 19 |

---

## Repository map

| Path | Role |
| --- | --- |
| `shared/` | `data_config`, `validate_hvac_data` |
| `csv_fdd_dashboard/` | Simple CSV → Plotly HTML + Flask + `dashboard_cache.py` |
| `fdd_dashboard_model/` | Enhanced catalogs + VAV loaders |
| `data/` | Pointer docs only — no bulk CSV in git |
| `vibe19_agent_spec/` | This tree |

---

## Skill index

| Skill | When |
| --- | --- |
| `skills/vibe19-hvac-data-import/` | New site CSV tree, manifest, env paths |
| `skills/vibe19-pandas-fdd-rules/` | Cookbook rule → pandas engine |
| `skills/vibe19-plotly-dashboard/` | HTML pages, Plotly figures, seasons |
| `skills/vibe19-flask-analyst-ui/` | Tune sliders, notes, deploy mode |
| `skills/vibe19-deploy-packaging/` | Client zip, Docker |
| `skills/vibe19-point-catalog/` | VAV/AHU model, terminal faults |

Cursor users: mirror skills under repo `.cursor/skills/` if desired; **`vibe19_agent_spec/skills/`** is canonical.

---

## Reference example sites (development only — not the product)

These buildings exist to **test the template** against real CSV quirks. Forks point at their own `DATA_ROOT` and building id.

| Key | Value |
| --- | --- |
| Data root | Set via `HVAC_DATA_ROOT` or `data_paths.local.yaml` |
| Example buildings | `BUILDING_100`, `BUILDING_50` (arbitrary ids under your tree) |
| Grid | Read from `manifest.json` (`grid_minutes`); **mixed grid OK** (e.g. AHU 15-min + VAV 5-min) |
| VAV | Per-box folders under `{BUILDING}/VAV/{id}/` when exported |
| Session log | [`SESSION_LOG.md`](SESSION_LOG.md) — reference-example dev diary |

Never hardcode customer-specific paths or building labels in committed code.

---

## Smoke scripts

```bash
cd vibe_code_apps_19
python validate_data.py

cd csv_fdd_dashboard
python -m pytest test_economizer_diagnostics.py test_sensor_qa.py -q
python generate_dashboard.py
```

After each task: update **`BUILD_CHECKPOINTS.md`** (done + next slice) and append **`SESSION_LOG.md`** when non-trivial.
