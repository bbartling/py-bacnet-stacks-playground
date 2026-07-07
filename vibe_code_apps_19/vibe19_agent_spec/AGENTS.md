# Vibe19 agent workspace — orientation

Plain Markdown on disk is the source of truth for **Cursor**, **Codex CLI**, and **OpenClaw**-style agents. Product code lives in `vibe_code_apps_19/`; orchestration lives in **`vibe19_agent_spec/`**.

**Primary agent prompt (paste into new sessions):** [`../AGENTS.md`](../AGENTS.md)

**External references:**

- [Open-FDD](https://bbartling.github.io/open-fdd/) — platform docs, CSV import, SQL rules
- [Pandas FDD Cookbook](https://bbartling.github.io/open-fdd/rules/cookbook/pandas-cookbook.html) — **source of truth for rule expressions in this app**

---

## Bootstrap order (each agent wake)

1. **`../AGENTS.md`** — mission, non-negotiables, repo map
2. **`BUILD_CHECKPOINTS.md`** — pick **one** slice from “Next for agent (ordered)”
3. **`DATA_CONTRACT.md`** — if touching imports or new building
4. **`skills/<topic>/SKILL.md`** — when checkpoint names a topic
5. **`docs/DASHBOARD_UI_SPEC.md`** — if adding/changing HTML pages
6. **`docs/OPENFDD_PARITY.md`** — if adding FDD rules

Do **not** paste entire Open-FDD doc sites into prompts — link and implement the specific rule section.

---

## Human vs agent roles

| Responsibility | Human | Agent |
| --- | --- | --- |
| Client CSV export / Open-FDD import | Provides `DATA_ROOT` path | Validates layout, documents gaps |
| Point mapping sign-off | Approves `point_role` → column maps | Drafts mapping JSON from `columns.csv` |
| Fault thresholds | Tunes with analyst panel | Exposes params in `dashboard_params.py` |
| Client delivery | Uploads PA zip / Drive | Builds `package_dashboard.py` / `build_pa_deploy.py` |
| BACnet / live writes | Field work | **Out of scope** for App 19 |

---

## Repository map

| Path | Role |
| --- | --- |
| `shared/` | `data_config`, `validate_hvac_data` |
| `csv_fdd_dashboard/` | Simple CSV → Plotly HTML + Flask |
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
| `skills/vibe19-deploy-packaging/` | Client zip, PythonAnywhere |
| `skills/vibe19-point-catalog/` | VAV/AHU model, terminal faults |

Cursor users: mirror skills under repo `.cursor/skills/` if desired; **`vibe19_agent_spec/skills/`** is canonical.

---

## Default reference site (development)

| Key | Value |
| --- | --- |
| Data root | Set via `HVAC_DATA_ROOT` or `data_paths.local.yaml` |
| Buildings | `BUILDING_100`, `BUILDING_50` |
| Grid | Read from `manifest.json` (`grid_minutes`, typically 5 → 300 s poll) |
| VAV | Per-box folders under `{BUILDING}/VAV/{id}/` |

Never hardcode customer-specific paths in committed code (use `data_paths.local.yaml`).

---

## Smoke scripts

```bash
cd vibe_code_apps_19
python validate_data.py

cd csv_fdd_dashboard
python -m pytest test_economizer_diagnostics.py test_sensor_qa.py -q
python generate_dashboard.py
```

After each task: update **`BUILD_CHECKPOINTS.md`** (done + next slice).
