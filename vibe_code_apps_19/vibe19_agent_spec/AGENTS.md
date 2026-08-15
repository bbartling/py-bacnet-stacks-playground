# Vibe19 agent workspace — orientation

Plain Markdown on disk is the source of truth for **Cursor**, **Codex CLI**, and similar agents. Product code lives in `vibe_code_apps_19/`; orchestration lives in **`vibe19_agent_spec/`**.

**Primary agent prompt (paste into new sessions):** [`../AGENTS.md`](../AGENTS.md)

**Quick link — zip package layout:** [`../docs/PACKAGE_SPEC.md`](../docs/PACKAGE_SPEC.md) (`openfdd_package_v1`)

## Shared volume handoff (co-located vibe20)

When Studio WattLab (vibe20) shares `$WATTLAB_HOST_WORKSPACE` (e.g. `~/wattlab_workspace`):

1. Export WattLab dump zip to **`$WATTLAB_HOST_WORKSPACE/uploads/dump/`** (not only a local Downloads folder).
2. Stamp dump `data_window` / telemetry years on Export README — vibe20 agents must see if dump weather (often partial current year) ≠ utility bill years.
3. Fuel/campus CSVs → `uploads/energy/`; bills for G14 → `reports/utility_bills.csv`.
4. vibe20 agents use `docker exec vibe20 wattlab …` on the same volume — see vibe20 `AGENT_DOCKER_WORKSPACE.md`.

**App:** Educational **Streamlit + pandas** FDD demo (`streamlit_app.py`).

**UI stack (do not confuse):** Native **Streamlit only** — not FastAPI/Flask embedding
Streamlit, not a mid-run HTTP server. Headless agent path is in-process Python
(`app/agent_api.py` + `scripts/agent_afdd.py`), then bootstrap JSON → Streamlit
session. Production Rust Open-FDD is a **separate** repo.

**Not this repo:** Production Rust/DataFusion Open-FDD → `C:\Users\ben\Documents\open-fdd`

---

## AI agent quick rules (read first)

1. **Never commit client CSV history** — browse/paste a local building folder; keep trees out of git.
2. **62 canonical diagnostics on OpenFDD 4.4.1** — never silently omit; use `SKIPPED_MISSING_ROLES` / `SKIPPED_EQUIPMENT_OFF` / `NOT_APPLICABLE_EQUIPMENT_TYPE`. (Manifest `rule_catalog_version` may still read `59-diagnostics+4-sql-analytics`.)
3. **No Rust / DataFusion / FastAPI / Flask / Haystack RDF / Oxigraph** in this app.
4. **Rules follow Open-FDD pandas cookbook** — raw mask → optional operational gate → `confirm_fault()` → rollup hours.
5. **Operational gates** — most rules require fan/pump/compressor proof; see `docs/OPERATIONAL_GATES.md`. Prefer `fan_status` over `fan_cmd`.
6. **Web OAT by default** — analytics / free-cool / OAT bins / physics rules prefer `wx_oa_t` via `oa_t_effective` (`app/weather_resolver.py`). OAT-METEO requires both BAS and web.
7. **Haystack point names end-to-end** — `siteRef` / `equip` / `device` / `points` map directly to CSV columns; rules read the same names (`discharge-air-temp`, …). See `docs/HAYSTACK_LIKE_MAPPING_GUIDE.md`. Optional package-root `column_map.json` is auto-loaded.
8. **Building id = folder name** — any site; BUILDING_100 is a demo label only.
9. **Update this spec after meaningful changes** — skills + `SESSION_LOG.md`.
10. Run **`python -m pytest -q`** before claiming done (or `scripts/run_tests_local.ps1` on Windows).
11. **Agent API (headless, not FastAPI)** — `app/agent_api.py` + `scripts/agent_afdd.py` for load/run/export without opening the browser. Same pandas cookbook; **no** FastAPI/Flask product UI.
12. **Motor charts ≠ compressor proof** — motor/pump/DX status first for weekly motor charts. No pump in data model → **omit** that motor series (never invent motor hours from leave temp). Prefer mapped fan/pump roles over column-name invent. **CHW pump status/command alone does not prove compressor operation** for mech-cooling OAT bins (rule 13).
13. **Mech-cooling OAT bins = compressor devices only** — chillers/CHW plants, DX AHU/RTU, cooling-mode HP, VRF outdoor, typed compressor equipment. Acceptable proof: compressor/chiller **status**, verified **command**, analog **power/current**. Never pump-alone, fan status, cooling demand, or `clg_valve_pct` / chilled-water AHU valves. Sidebar **Use mapped mechanical-cooling status proof** (default checked): status → verified cmd → amps/power. Unchecked: CHW plants may use **CHW leave proof max °F** (`inferred: chw_leave_temp`; never on CHW AHU valves). Coverage: `eligible_no_runtime` for idle mapped compressors. Aggregates: **device-hours** (sum) + **any-active** (union); one running device ⇒ aggregates equal. Sort bins by `bin_start` cold→hot. `include_ahu_chw_valve` deprecated/ignored. **WattLab dump** always `run_rules` complete cookbook; default profile **`summary`** / schema **`wattlab_dump_v3`** (shared `telemetry/`; legacy `fdd_timeseries/` optional). Publish GHCR via `vibe19-ghcr.yml` only — **do not publish Vibe 20** for this change.
14. **Occupancy calendar is canonical** — Overview weekly time pickers **always** drive `occ_mode` for SCHED-1. Do not re-add “Apply calendar → occ_mode” checkbox or casually remove the schedule UI.
15. **Typed equipment is canonical** — stamp `equipType` in column maps; `resolve_equipment_type` (attrs → map → id). RTU→AHU, heatPump→HP. RCx/rules use typed equip, not id substrings.
16. Smoke UI: `py -3.14 scripts/smoke_streamlit_app.py` (AppTest, 0 exceptions).
17. **Agent → Streamlit**: after `agent_afdd.py --run-all`, open http://localhost:8501 — `.last_agent_session.json` / `VIBE19_BOOTSTRAP` auto-loads package + dialed params. On Cloud: download/upload `session_config.json` (sidebar) instead of server paths. **Browser zip uploads** also persist across refresh via `.last_browser_session.json` (`app/browser_session.py`) until **Clear session**; set `VIBE19_BROWSER_AUTOLOAD=0` in AppTest/CI.
18. **Custom rules** — boilerplate in `app/rules/custom_boilerplate.py`; agent edits `app/rules/custom_rules.py` (`CUSTOM-*` ids only). Spec: `vibe19_agent_spec/docs/CUSTOM_RULES.md`.
19. **Make it your own** — DB ingest pattern, branding, deploy forks: [`docs/CUSTOMIZE.md`](docs/CUSTOMIZE.md). **Browser upload 500 MB** / **agent-path 2048 MB** package defaults; GHCR: `ghcr.io/<owner>/vibe19` — see [`../docs/DOCKER.md`](../docs/DOCKER.md).
20. **Dashboard contract** — RCx reset scatters (HW/CHW leave vs web OAT, CW/tower vs wet-bulb), AHU SAT vs web OAT, and AHU duct-static **box** are required. Do not delete presets in `REQUIRED_RCX_PRESET_IDS`. Overview must keep **Data inspection** (raw CSV Plotly stack) + BAS vs web OAT overlay. See [`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md).
21. **FDD Plots = rule validation cards** — all applicable cookbook rules for the selected device (params + required/mapped points); one Plotly via plot focus; **Sensor health — per sensor**. Shared builder: `app/rule_card.py`. Spec: [`docs/PLOTS_DOCX_VALIDATION.md`](docs/PLOTS_DOCX_VALIDATION.md). Per-rule Haystack tags / sliders / series: [`docs/RULE_PLOT_CATALOG.md`](docs/RULE_PLOT_CATALOG.md). Keep **Data Model** (`app/data_model_tree.py`).
22. **RCx Plots** — family → preset (`RCX_FAMILY_ORDER`); zone comfort donut; opt-in coverage. **Two reporting products on Overview:** (1) static Generic RCx (`app/docx_report.py`); (2) button-triggered Engineering Findings (`app/reporting/`, detection ≠ finding). Spec: [`docs/RCX_PLOTS.md`](docs/RCX_PLOTS.md), [`docs/PLOTS_DOCX_VALIDATION.md`](docs/PLOTS_DOCX_VALIDATION.md), skill [`skills/vibe19-engineering-report/SKILL.md`](skills/vibe19-engineering-report/SKILL.md).
23. **Analytics golden baseline** — before perf/analytics edits run `pytest tests/test_analytics_golden.py`; regen with `VIBE19_UPDATE_ANALYTICS_GOLDEN=1`. Harness: `app/analytics_baseline.py`.
24. **Perf bottlenecks** — eager Export/FDD DOCX + `rcx_preset_coverage`, Folder cache copies, rule-batch frame copies, `iterrows` scatters. Do not reintroduce eager `st.tabs`. Findings: [`docs/PERF_BOTTLENECKS.md`](docs/PERF_BOTTLENECKS.md).
25. **README + GHCR pull-latest stay current** — after Docker/GHCR/deploy changes (and whenever shipping a new image), keep **`../README.md` → Docker / GHCR** and **`../docs/DOCKER.md`** aligned with the easy-button update path:
    - Image tip: `ghcr.io/bbartling/vibe19:latest` (same tip as `:develop` while default branch is `develop`)
    - Scripts: `scripts/docker_update_vibe19.sh` / `scripts/docker_update_vibe19.ps1` (pull + recreate — containers never auto-update)
    - Clarify that GitHub Packages “Latest” on a `sha-…` version ≠ Docker `:latest` and ≠ auto-update
    - Do **not** leave README stuck on stale one-shot `--rm` examples as the only path
    - Detail: [`docs/DOCKER.md`](../docs/DOCKER.md) · workflow: `../../.github/workflows/vibe19-ghcr.yml`
26. **Dead-slider ban** — every declared sidebar param except `confirm_min` must change the **raw** fault mask. Never subtract the same tol from both sides of an inequality (e.g. `(mat - tol) < min(rat - tol, oat - tol)` cancels). When adding a slider, add a case in `tests/test_rule_param_sensitivity.py`. Plotly downsample-on-fault-edges is **not** data smoothing — rule math never smooths historian series.
27. **Confirm-default contract** — every rule's `confirm_min` slider default must equal `confirm_seconds / 60`. `_ensure_confirm_param_defaults()` enforces this so a hard-coded 5.0 never silently overrides longer windows (FC2=10 min, FC4=60, CHW-NOLOAD-1=30, PID-HUNT-1=0). Test: `tests/test_confirm_and_duration.py`.
28. **Param direction hints** — `CookbookParam.direction` is `"fewer"` (↑ → fewer faults), `"stricter"` (↑ → more faults), or `""`. Sidebar stores **only changed** params (diffs from defaults). Compare **fault hours**, not only `fault_pct` — raising startup delay shrinks the active denominator so % can rise while hours stay flat.
29. **Dt-aware confirm / hours** — `confirm_fault` and `hours_true` use actual DatetimeIndex deltas when present (fallback: `poll_seconds` row-count). Mixed param fingerprints in `batch_results` trigger a Results warning after partial re-runs.
30. **GHCR containers must always be good multi-arch** — never ship an amd64-only tip, never leave `:latest` / `:develop` pointing at a broken/missing manifest. Publish via `.github/workflows/vibe19-ghcr.yml` only:
    - **QEMU** `platforms: amd64,arm64` + Buildx **`linux/amd64,linux/arm64`** on every push / `workflow_dispatch` (PR smoke may stay amd64-only; no push).
    - Workflow **must** run the **Verify multi-arch manifest** step (asserts both arches in the index).
    - If `docker pull ghcr.io/…/vibe19:latest` fails with `manifest … not found` / missing blob digests: **`gh workflow run vibe19-ghcr.yml --ref develop -f no_cache=true`** (Do not “fix” by retagging alone or pushing a single-arch image.)
    - After publish: `docker pull …:latest` and `docker buildx imagetools inspect …:latest` must show **linux/amd64** and **linux/arm64**.
    - Never delete GHCR package versions that tags still reference; prefer no-cache rebuild over pruning shared layers.
    - Detail: [`../docs/DOCKER.md`](../docs/DOCKER.md) → **Publishing good containers (agents)**.

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
5f. **`../README.md` (Docker / GHCR)** + **`../docs/DOCKER.md`** — when shipping images or changing pull/run instructions; keep easy-button pull-latest scripts documented; enforce **rule 30** (QEMU amd64+arm64, verify manifest, no-cache rebuild if tags are broken)
5g. **`skills/vibe19-engineering-report/SKILL.md`** — when editing Engineering Findings / evidence review / report DOCX+JSON
6. **`skills/vibe19-pandas-fdd-rules/SKILL.md`** — when editing rules
7. **`skills/vibe19-hvac-data-import/SKILL.md`** — when touching CSV layout / BUILDING trees
8. **`docs/OPERATIONAL_GATES.md`** / **`docs/RCX_PLOTS.md`** / **`docs/STREAMLIT_RULE_INVENTORY.md`** as needed

---

## Repository map

| Path | Role |
| --- | --- |
| `streamlit_app.py` | Streamlit UI entry (lazy radio sections + sidebar) |
| `app/browser_session.py` | Zip upload pointer — refresh persistence until Clear session |
| `app/package_io.py` | Safe zip/dir ingest + size caps / size report |
| `app/agent_api.py` | Headless AgentDataset / AgentRun load·run·export |
| `app/bootstrap.py` | Agent → Streamlit session handoff |
| `scripts/agent_afdd.py` | CLI wrapper for agent_api |
| `app/weather_resolver.py` | Effective OAT policy (web primary) |
| `app/charts.py` | Rule plots, RCx multi-series / box / OAT scatter |
| `app/rule_card.py` | FDD Plots/DOCX shared validation card content |
| `app/docx_report.py` | Static Generic RCx template loader (+ legacy helper paths) |
| `app/reporting/` | Engineering Findings (evidence review → DOCX/JSON/charts) |
| `app/report_downloads.py` | Overview Generic RCx + Engineering Findings panel |
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
