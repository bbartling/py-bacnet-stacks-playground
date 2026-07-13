# Vibe19 agent workspace — orientation

Plain Markdown on disk is the source of truth for **Cursor**, **Codex CLI**, and similar agents. Product code lives in `vibe_code_apps_19/`; orchestration lives in **`vibe19_agent_spec/`**.

**Primary agent prompt (paste into new sessions):** [`../AGENTS.md`](../AGENTS.md)

**App:** Educational **Streamlit + pandas** 50-rule FDD demo (`streamlit_app.py`).

**Not this repo:** Production Rust/DataFusion Open-FDD → `C:\Users\ben\Documents\open-fdd`

---

## AI agent quick rules (read first)

1. **Never commit client CSV history** — browse/paste a local building folder; keep trees out of git.
2. **53 canonical rules** — never silently omit; use `SKIPPED_MISSING_ROLES` / `SKIPPED_EQUIPMENT_OFF` / `NOT_APPLICABLE_EQUIPMENT_TYPE`.
3. **No Rust / DataFusion / FastAPI / Flask / Haystack RDF / Oxigraph** in this app.
4. **Rules follow Open-FDD pandas cookbook** — raw mask → optional operational gate → `confirm_fault()` → rollup hours.
5. **Operational gates** — most rules require fan/pump/compressor proof; see `docs/OPERATIONAL_GATES.md`. Prefer `fan_status` over `fan_cmd`.
6. **Web OAT by default** — analytics / free-cool / OAT bins / physics rules prefer `wx_oa_t` via `oa_t_effective` (`app/weather_resolver.py`). OAT-METEO requires both BAS and web.
7. **Haystack-like authoring** — `siteRef` / `equip` / `device` / `points` normalize to cookbook roles; see `docs/HAYSTACK_LIKE_MAPPING_GUIDE.md`. Optional package-root `column_map.json` is auto-loaded.
8. **Building id = folder name** — any site; BUILDING_100 is a demo label only.
9. **Update this spec after meaningful changes** — skills + `SESSION_LOG.md`.
10. Run **`python -m pytest -q`** before claiming done (or `scripts/run_tests_local.ps1` on Windows).
11. **Agent API** — `app/agent_api.py` + `scripts/agent_afdd.py` for headless load/run/export (no FastAPI/Flask).
12. **Runtime proof** — motor/pump/DX status first. No pump in data model → **omit** chiller from run-hours (never fake hours from leave temp). Prefer mapped fan/pump roles over column-name invent.
13. **Mech-cooling OAT bins = mechanical compressors / plant only** — chiller plant (chiller + preferably `chw_pump_status` / cmd) **or** AHU / heat pump / RTU with **DX / compressor** roles (`compressor_status`, `dx_stage`, `dx_cool_cmd`, `cool_stage`, `dx_cooling`). **Never** use `clg_valve_pct` / CHW cooling-valve % (often modulate with no chilled water). Do **not** re-add UI/session toggle; `include_ahu_chw_valve` is deprecated, always False/ignored. Sort bins by `bin_start` cold→hot.
14. **Occupancy calendar is canonical** — Overview weekly time pickers **always** drive `occ_mode` for SCHED-1. Do not re-add “Apply calendar → occ_mode” checkbox or casually remove the schedule UI.
15. **Typed equipment is canonical** — stamp `equipType` in column maps; `resolve_equipment_type` (attrs → map → id). RTU→AHU, heatPump→HP. RCx/rules use typed equip, not id substrings.
16. Smoke UI: `py -3.14 scripts/smoke_streamlit_app.py` (AppTest, 0 exceptions).
17. **Agent → Streamlit**: after `agent_afdd.py --run-all`, open http://localhost:8501 — `.last_agent_session.json` / `VIBE19_BOOTSTRAP` auto-loads package + dialed params. On Cloud: download/upload `session_config.json` (sidebar) instead of server paths.
18. **Custom rules** — boilerplate in `app/rules/custom_boilerplate.py`; agent edits `app/rules/custom_rules.py` (`CUSTOM-*` ids only). Spec: `vibe19_agent_spec/docs/CUSTOM_RULES.md`.
19. **Make it your own** — DB ingest pattern, branding, deploy forks: [`docs/CUSTOMIZE.md`](docs/CUSTOMIZE.md). **Browser upload 500 MB** / **agent-path 2048 MB** package defaults; GHCR: `ghcr.io/<owner>/vibe19` — see [`../docs/DOCKER.md`](../docs/DOCKER.md).
20. **Dashboard contract** — RCx reset scatters (HW/CHW leave vs web OAT, CW/tower vs wet-bulb), AHU SAT vs web OAT, and AHU duct-static **box** are required. Do not delete presets in `REQUIRED_RCX_PRESET_IDS`. See [`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md).
21. **FDD Plots = rule validation cards** — all applicable cookbook rules for the selected device (params + required/mapped points); one Plotly via plot focus; one-click **Download FDD DOCX** with **`PLACE PLOT HERE`** stubs. Shared builder: `app/rule_card.py`. Spec: [`docs/PLOTS_DOCX_VALIDATION.md`](docs/PLOTS_DOCX_VALIDATION.md). Per-rule Haystack tags / sliders / series: [`docs/RULE_PLOT_CATALOG.md`](docs/RULE_PLOT_CATALOG.md). Keep **Data Model** + DOCX APIs (`app/docx_report.py`, `app/data_model_tree.py`).
22. **RCx Plots** — family → preset (`RCX_FAMILY_ORDER`); opt-in coverage + catalog DOCX. Spec: [`docs/RCX_PLOTS.md`](docs/RCX_PLOTS.md).
23. **Analytics golden baseline** — before perf/analytics edits run `pytest tests/test_analytics_golden.py`; regen with `VIBE19_UPDATE_ANALYTICS_GOLDEN=1`. Harness: `app/analytics_baseline.py`.
24. **Perf bottlenecks** — eager Export/FDD DOCX + `rcx_preset_coverage`, Folder cache copies, rule-batch frame copies, `iterrows` scatters. Do not reintroduce eager `st.tabs`. Findings: [`docs/PERF_BOTTLENECKS.md`](docs/PERF_BOTTLENECKS.md).
25. **README + GHCR pull-latest stay current** — after Docker/GHCR/deploy changes (and whenever shipping a new image), keep **`../README.md` → Docker / GHCR** and **`../docs/DOCKER.md`** aligned with the easy-button update path:
    - Image tip: `ghcr.io/bbartling/vibe19:latest` (same tip as `:develop` while default branch is `develop`)
    - Scripts: `scripts/docker_update_vibe19.sh` / `scripts/docker_update_vibe19.ps1` (pull + recreate — containers never auto-update)
    - Clarify that GitHub Packages “Latest” on a `sha-…` version ≠ Docker `:latest` and ≠ auto-update
    - Do **not** leave README stuck on stale one-shot `--rm` examples as the only path
    - Detail: [`docs/DOCKER.md`](../docs/DOCKER.md) · workflow: `../../.github/workflows/vibe19-ghcr.yml`

---

## Bootstrap order (each agent wake)

1. **`../AGENTS.md`** — mission and non-negotiables
2. **AI quick rules above**
3. **`docs/CUSTOMIZE.md`** — when forking branding / DB / custom faults / deploy
4. **`skills/vibe19-streamlit-demo/SKILL.md`** — primary skill
5. **`skills/vibe19-plotly-dashboard/SKILL.md`** — FDD Plots cards + RCx Plots
5b. **`docs/DASHBOARD_CONTRACT.md`** — required RCx presets + FDD Plots/DOCX freeze + analytics goldens (do not delete)
5c. **`docs/PLOTS_DOCX_VALIDATION.md`** — when editing FDD Plots / FDD DOCX / rule cards
5d. **`docs/RULE_PLOT_CATALOG.md`** — per-rule chart points, Haystack tags, sliders (all 50)
5e. **`docs/PERF_BOTTLENECKS.md`** — why the UI is slow; what not to regress; safe follow-ups
5f. **`../README.md` (Docker / GHCR)** + **`../docs/DOCKER.md`** — when shipping images or changing pull/run instructions; keep easy-button pull-latest scripts documented
6. **`skills/vibe19-pandas-fdd-rules/SKILL.md`** — when editing rules
7. **`skills/vibe19-hvac-data-import/SKILL.md`** — when touching CSV layout / BUILDING trees
8. **`docs/OPERATIONAL_GATES.md`** / **`docs/RCX_PLOTS.md`** / **`docs/STREAMLIT_RULE_INVENTORY.md`** as needed

---

## Repository map

| Path | Role |
| --- | --- |
| `streamlit_app.py` | Streamlit UI entry (lazy radio sections + sidebar) |
| `app/package_io.py` | Safe zip/dir ingest + size caps / size report |
| `app/agent_api.py` | Headless AgentDataset / AgentRun load·run·export |
| `app/bootstrap.py` | Agent → Streamlit session handoff |
| `scripts/agent_afdd.py` | CLI wrapper for agent_api |
| `app/weather_resolver.py` | Effective OAT policy (web primary) |
| `app/charts.py` | Rule plots, RCx multi-series / box / OAT scatter |
| `app/rule_card.py` | FDD Plots/DOCX shared validation card content |
| `app/docx_report.py` | Equipment FDD / data-model / analytics Word reports |
| `app/data_model_tree.py` | Data Model inventory tree |
| `app/dashboard_contract.py` | Frozen UI sections + chart/DOCX entrypoints |
| `app/rcx_plots.py` | Prebuilt RCx presets + families + summary/outlier stats |
| `app/ui_rcx_tab.py` | **RCx Plots** tab UI (family → preset; lazy DOCX/coverage) |
| `app/analytics.py` | Motor hours, mech-cooling OAT bins (web OAT default) |
| `app/analytics_baseline.py` | Golden fingerprint harness for analytics / RCx / rule digests |
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
| `vibe19_agent_spec/docs/PLOTS_DOCX_VALIDATION.md` | FDD Plots cards + FDD DOCX contract |
| `vibe19_agent_spec/docs/RULE_PLOT_CATALOG.md` | All 50 rules: Haystack tags, plot series, sliders |
| `scripts/docker_update_vibe19.sh` / `.ps1` | **Easy button:** `docker pull` tip + recreate long-running container |
| `../README.md` → Docker / GHCR | Newbie pull-latest / long-running recipe (keep in sync) |
| `../docs/DOCKER.md` | Full Docker + GHCR (tags, Pi, bootstrap mounts) |
| `.github/workflows/vibe19-ghcr.yml` | Publishes `ghcr.io/<owner>/vibe19` (`:latest`, `:develop`, `:sha-…`) |
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
| `skills/vibe19-plotly-dashboard/` | FDD Plots validation cards + **RCx Plots** presets + DOCX stubs |
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
