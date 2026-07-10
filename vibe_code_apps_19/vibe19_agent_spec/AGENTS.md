# Vibe19 agent workspace — orientation

Plain Markdown on disk is the source of truth for **Cursor**, **Codex CLI**, and similar agents. Product code lives in `vibe_code_apps_19/`; orchestration lives in **`vibe19_agent_spec/`**.

**Primary agent prompt (paste into new sessions):** [`../AGENTS.md`](../AGENTS.md)

**App:** Educational **Streamlit + pandas** 50-rule FDD demo (`streamlit_app.py`).

**Not this repo:** Production Rust/DataFusion Open-FDD → `C:\Users\ben\Documents\open-fdd`

---

## AI agent quick rules (read first)

1. **Never commit client CSV history** — browse/paste a local building folder; keep trees out of git.
2. **50 canonical rules** — never silently omit; use `SKIPPED_MISSING_ROLES` / `SKIPPED_EQUIPMENT_OFF` / `NOT_APPLICABLE_EQUIPMENT_TYPE`.
3. **No Rust / DataFusion / FastAPI / Flask / Haystack RDF / Oxigraph** in this app.
4. **Rules follow Open-FDD pandas cookbook** — raw mask → optional operational gate → `confirm_fault()` → rollup hours.
5. **Operational gates** — most rules require fan/pump/compressor proof while evaluating; see `docs/OPERATIONAL_GATES.md`. Prefer `fan_status` over `fan_cmd`.
6. **Haystack-like authoring** — `siteRef` / `equip` / `device` / `points` (`discharge-air-temp`, …) normalize to cookbook roles; see `docs/HAYSTACK_LIKE_MAPPING_GUIDE.md`.
7. **Building id = folder name** — any site; BUILDING_100 is a demo label only.
8. **Update this spec after meaningful changes** — skills + `SESSION_LOG.md`.
9. Run **`python -m pytest -q`** before claiming done.

---

## Bootstrap order (each agent wake)

1. **`../AGENTS.md`** — mission and non-negotiables
2. **AI quick rules above**
3. **`skills/vibe19-streamlit-demo/SKILL.md`** — primary skill
4. **`skills/vibe19-pandas-fdd-rules/SKILL.md`** — when editing rules
5. **`skills/vibe19-hvac-data-import/SKILL.md`** — when touching CSV layout / BUILDING trees
6. **`docs/STREAMLIT_AGENT_SPEC.md`** / **`docs/STREAMLIT_RULE_INVENTORY.md`** as needed

Install official Streamlit widget skills (optional): [`streamlit skills`](https://docs.streamlit.io/develop/api-reference/cli/skills)

---

## Repository map

| Path | Role |
| --- | --- |
| `streamlit_app.py` | Streamlit UI entry |
| `app/` | Rules, role map, loaders, charts, mapping wizard |
| `configs/` | Rule inventory, defaults, role_map.yaml |
| `tests/` | Pytest |
| `data/` | Pointer docs only — no bulk CSV in git |
| `vibe19_agent_spec/` | This tree (skills + agent docs) |

---

## Skill index

| Skill | When |
| --- | --- |
| `skills/vibe19-streamlit-demo/` | **Primary** — run app, tabs, CSV upload, data modes |
| `skills/vibe19-pandas-fdd-rules/` | Cookbook rule → pandas |
| `skills/vibe19-hvac-data-import/` | BUILDING_* CSV tree layout / validation |
| `skills/vibe19-point-catalog/` | VAV/AHU point roles |
| `skills/vibe19-plotly-dashboard/` | Plotly charts inside Streamlit |
| `skills/vibe19-flask-analyst-ui/` | **RETIRED** → streamlit-demo |
| `skills/vibe19-haystack-rdf/` | **RETIRED** → streamlit-demo |
| `skills/vibe19-deploy-packaging/` | **RETIRED** → streamlit-demo / Open-FDD |

---

## Smoke scripts (before claiming done)

```powershell
cd vibe_code_apps_19
python -m pip install -e ".[dev]"
python -m pytest -q
streamlit run streamlit_app.py
```

After each task: append **`SESSION_LOG.md`** when non-trivial.
