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
5. **Operational gates** — most rules require fan/pump/compressor proof; see `docs/OPERATIONAL_GATES.md`. Prefer `fan_status` over `fan_cmd`.
6. **Web OAT by default** — analytics / free-cool / OAT bins / physics rules prefer `wx_oa_t` via `oa_t_effective` (`app/weather_resolver.py`). OAT-METEO requires both BAS and web.
7. **Haystack-like authoring** — `siteRef` / `equip` / `device` / `points` normalize to cookbook roles; see `docs/HAYSTACK_LIKE_MAPPING_GUIDE.md`. Optional package-root `column_map.json` is auto-loaded.
8. **Building id = folder name** — any site; BUILDING_100 is a demo label only.
9. **Update this spec after meaningful changes** — skills + `SESSION_LOG.md`.
10. Run **`python -m pytest -q`** before claiming done (or `scripts/run_tests_local.ps1` on Windows).
11. **Agent API** — `app/agent_api.py` + `scripts/agent_afdd.py` for headless load/run/export (no FastAPI/Flask).
12. **Runtime proof** — motor/pump/DX status first. No pump in data model → **omit** chiller from run-hours (never fake hours from leave temp).
13. **Mech-cooling OAT bins** — chillers + DX compressors only; **never** CHW cooling valves (often modulate with no chilled water). Sort bins by `bin_start` cold→hot.
14. Smoke UI: `py -3.14 scripts/smoke_streamlit_app.py` (AppTest, 0 exceptions).
15. **Agent → Streamlit**: after `agent_afdd.py --run-all`, open http://localhost:8501 — `.last_agent_session.json` / `VIBE19_BOOTSTRAP` auto-loads package + dialed params. On Cloud: download/upload `session_config.json` (sidebar) instead of server paths.
16. **Custom rules** — boilerplate in `app/rules/custom_boilerplate.py`; agent edits `app/rules/custom_rules.py` (`CUSTOM-*` ids only). Spec: `vibe19_agent_spec/docs/CUSTOM_RULES.md`.
17. **Make it your own** — DB ingest pattern, branding, deploy forks: [`docs/CUSTOMIZE.md`](docs/CUSTOMIZE.md) (~90% template). Package default safety limit **500 MB** (zip + expanded).

---

## Bootstrap order (each agent wake)

1. **`../AGENTS.md`** — mission and non-negotiables
2. **AI quick rules above**
3. **`docs/CUSTOMIZE.md`** — when forking branding / DB / custom faults / deploy
4. **`skills/vibe19-streamlit-demo/SKILL.md`** — primary skill
5. **`skills/vibe19-plotly-dashboard/SKILL.md`** — Plots + RCx Plots
6. **`skills/vibe19-pandas-fdd-rules/SKILL.md`** — when editing rules
7. **`skills/vibe19-hvac-data-import/SKILL.md`** — when touching CSV layout / BUILDING trees
8. **`docs/OPERATIONAL_GATES.md`** / **`docs/RCX_PLOTS.md`** / **`docs/STREAMLIT_RULE_INVENTORY.md`** as needed

---

## Repository map

| Path | Role |
| --- | --- |
| `streamlit_app.py` | Streamlit UI entry (tabs + sidebar) |
| `app/package_io.py` | Safe zip/dir ingest + size caps / size report |
| `app/agent_api.py` | Headless AgentDataset / AgentRun load·run·export |
| `app/bootstrap.py` | Agent → Streamlit session handoff |
| `scripts/agent_afdd.py` | CLI wrapper for agent_api |
| `app/weather_resolver.py` | Effective OAT policy (web primary) |
| `app/charts.py` | Rule plots, RCx multi-series / box / OAT scatter |
| `app/rcx_plots.py` | Prebuilt RCx presets + summary/outlier stats |
| `app/ui_rcx_tab.py` | **RCx Plots** tab UI |
| `app/analytics.py` | Motor hours, mech-cooling OAT bins (web OAT default) |
| `app/weather_psychrometrics.py` | Dewpoint (Magnus), wet-bulb (Stull), weather enrich |
| `app/occupancy.py` | Weekly occupancy calendar → `occ_mode` |
| `app/unit_system.py` | Imperial ↔ metric display conversion |
| `app/rules/` | Catalog, runner, gates, PID hunting |
| `app/rules/custom_boilerplate.py` | **Agent custom-rule templates** (pandas + z-score ML sketch) |
| `app/rules/custom_rules.py` | Agent appends `CUSTOM-*` rules here |
| `app/rules/custom_registry.py` | Canonical 50 + custom merge |
| `shared/branding.py` + `assets/` | Title + hero image |
| `vibe19_agent_spec/docs/CUSTOMIZE.md` | Fork guide (DB, branding, deploy) |
| `vibe19_agent_spec/docs/CUSTOM_RULES.md` | How to add special / site rules |
| `configs/` | Rule inventory, defaults, role_map.yaml |
| `scripts/csv_parity_check.py` | Run 50 rules on any building folder (CI/parity) |
| `tests/` | Pytest |
| `vibe19_agent_spec/` | This tree (skills + agent docs) |

**Do not recreate:** `haystack_rdf/`, `fdd_app/`, `csv_fdd_dashboard/`, `fdd_dashboard_model/`.

---

## Skill index

| Skill | When |
| --- | --- |
| `skills/vibe19-streamlit-demo/` | **Primary** — run app, tabs, folder browse |
| `skills/vibe19-plotly-dashboard/` | Rule plots + **RCx Plots** presets |
| `skills/vibe19-pandas-fdd-rules/` | Cookbook rule → pandas |
| `skills/vibe19-hvac-data-import/` | BUILDING_* CSV tree layout / validation |

---

## Smoke scripts (before claiming done)

```powershell
cd vibe_code_apps_19
python -m pip install -e ".[dev]"
python -m pytest -q
streamlit run streamlit_app.py
# optional parity on any site folder:
python scripts/csv_parity_check.py --building-folder PATH\to\MyBuilding
```

After each task: append **`SESSION_LOG.md`** when non-trivial.
