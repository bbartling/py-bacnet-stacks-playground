# Agent prompt — Streamlit pandas FDD demo (pinned OpenFDD catalog)

**Open-FDD (Rust/DataFusion):** `C:\Users\ben\Documents\open-fdd` — do **not** re-add Rust here.

**Quick link — zip package layout:** [`docs/PACKAGE_SPEC.md`](docs/PACKAGE_SPEC.md) (`openfdd_package_v1` manifest, per-equip Haystack maps, weather, size caps).

Codex / Claude / Cursor: paste this file as the session brief. For **Cloud zip preprocess**, also read [`docs/PACKAGE_SPEC.md`](docs/PACKAGE_SPEC.md).

## Mission

Maintain Vibe App 19 as an **educational Streamlit demo** consuming the **pinned PyPI OpenFDD cookbook** (`open-fdd[reporting]==4.4.0`, 62 diagnostic rules; catalog version string remains `59-diagnostics+4-sql-analytics`):

- `app/rules/` — thin shims to `open_fdd` (do not fork fault equations)
- `app/vav_health.py` — thin adapter for `open_fdd.analytics.vav_health`
- `app/rules/custom_boilerplate.py` + `custom_rules.py` — agent **CUSTOM-*** pandas / ML sketches
- `app/rules/runner.py` — skip / equipment-off / not-applicable execution
- `configs/rule_inventory.yaml` + `rule_defaults.yaml`
- `streamlit_app.py` — unified **Folder | Zip** picker, Overview, mapping, **Data Model**, run rules, **FDD Plots** (validation cards), **RCx Plots**, Metering, **Export** (WattLab dump zip for vibe20)
- `app/wattlab_dump.py` + `app/model_seed.py` — data-derived WattLab handoff (sensor stats, 24h diurnal profiles, setpoints, model seed); no interactive Energy Model wizard
- `app/package_io.py` — safe `openfdd_package_v1` zip ingest (Cloud + local)
- `app/agent_api.py` + `scripts/agent_afdd.py` — **Streamlit-free** agent load / run / export
- `app/weather_resolver.py` — web OAT primary / BAS fallback / OAT-METEO both-required
- `app/rcx_plots.py` + `app/ui_rcx_tab.py` — multi-equipment RCx charts
- `app/weather_psychrometrics.py` — web OAT / dewpoint / wet-bulb
- Spec: [`vibe19_agent_spec/docs/CUSTOM_RULES.md`](vibe19_agent_spec/docs/CUSTOM_RULES.md)

## Hard rules

1. **Pinned OpenFDD catalog (62 diagnostics on 4.4.0)** — never silently omit; use `SKIPPED_MISSING_ROLES`, `SKIPPED_EQUIPMENT_OFF`, or `NOT_APPLICABLE_EQUIPMENT_TYPE`. Agent extras use `CUSTOM-*` ids via `custom_rules.py` (see CUSTOM_RULES.md). Do not reimplement VAV-health math in Vibe19.
2. **No Rust / DataFusion / FastAPI / Flask / Haystack RDF / Oxigraph**
3. **No client historian trees in git** — local: browse folder; Cloud/shared: upload zip only (see package spec). Demo zip `data/demo_package_v1.zip` is OK
4. **Do not recreate** `haystack_rdf/`, `fdd_app/`, `fdd_dashboard_model/`
5. **Web OAT by default** for analytics / free-cool / physics rules needing OAT (`oa_t_effective`); OAT-METEO compares BAS vs web **only when both exist**
6. **`python -m pytest -q`** before done (Windows locked temp: `scripts/run_tests_local.ps1`)
7. **Keep `vibe19_agent_spec/` in sync** after UI/plot/rule changes (`SESSION_LOG.md`, skills, checkpoints). After Docker/GHCR ships: keep root **`README.md` Docker/GHCR** + **`docs/DOCKER.md`** documenting **pull-latest** (`:latest` / easy-button `scripts/docker_update_vibe19.(sh|ps1)`). Spec: [`vibe19_agent_spec/AGENTS.md`](vibe19_agent_spec/AGENTS.md) rules **25** and **30** (always publish **QEMU multi-arch** `linux/amd64` + `linux/arm64`; verify the manifest; use `workflow_dispatch` **`no_cache=true`** if tags point at missing blobs).
8. **Bad uploads must not crash the app** — raise/catch `PackageError`, show sidebar error, wipe temp dir; never leave uncaught exceptions on zip load
9. **Agent API is importable Python only** — `app/agent_api.py` (+ optional CLI). No HTTP API / background server.
10. **Motor charts ≠ compressor proof** — weekly motor charts still use designated `chw_pump_status` / `chw_pump_cmd` (or DX compressor on AHU/HP/RTU). No pump/status → **omit** that motor series (never invent motor hours from leave temp). **CHW pump status/command alone does not prove compressor operation** for mech-cooling OAT bins (see rule 11). Motor charts prefer mapped fan/pump roles before column-name heuristics.
11. **Mech-cooling OAT bins = compressor devices only** — chillers/CHW plants, DX AHU/RTU, cooling-mode heat pumps, VRF outdoor, typed compressor equipment. Acceptable proof: compressor/chiller **status**, verified **command**, analog **power/current** (unit-aware thresholds). **Never** treat CHW pump status/cmd, fan status, cooling demand, or AHU `clg_valve_pct` / chilled-water valve % as compressor proof. Sidebar **Use mapped mechanical-cooling status proof** (default checked): status → verified cmd → amps/power. Unchecked: CHW plants only may use **CHW leave proof max °F** labeled `inferred: chw_leave_temp` (never applied to CHW AHU valves; slider disabled while status proof is checked). Coverage: every cooling-capable device with `eligibility_state` / `activity_state` — mapped idle compressors are **`eligible_no_runtime`** (included), not excluded. Aggregates: **`aggregate_device_hours`** (sum) and **`aggregate_active_hours`** (union / any-compressor-active); when only one device ran, active-hours equals that device's hours. Bins sort cold→hot by `bin_start`. `include_ahu_chw_valve` stays deprecated/ignored. **WattLab dump** always re-runs the complete cookbook; default export profile is **`summary`** (`wattlab_dump_v3`).
12. **Occupancy calendar is canonical** — Overview weekly date/time pickers **always** write `occ_mode` for SCHED-1. Do not re-add an “Apply calendar → occ_mode” checkbox or casually remove the schedule UI.
13. **Typed equipment is canonical** — stamp `equipType` / `equipment_type` in `column_map.json` / role_map; resolver is `resolve_equipment_type` (attrs → map → id fallback). RTU → AHU; heatPump → HP. Do not invent RCx membership or rule kinds from id substrings alone.
14. **Dashboard contract** — keep RCx presets in `REQUIRED_RCX_PRESET_IDS` (HW/CHW leave vs web OAT, CW/tower vs wet-bulb, AHU SAT vs web OAT, duct-static box). Spec: [`vibe19_agent_spec/docs/DASHBOARD_CONTRACT.md`](vibe19_agent_spec/docs/DASHBOARD_CONTRACT.md). Keep **FDD Plots** validation cards via `app/rule_card.py` + **Sensor health**. Keep Overview **Data inspection** (raw CSV Plotly) and **BAS vs web OAT overlay**. Zip uploads persist across refresh until **Clear session** (`app/browser_session.py`). **Reporting:** button-triggered **FDD Engineering Findings Report** on **Run Rules** (`app/reporting/`, `render_engineering_findings_panel`) — evidence-reviewed findings; detection ≠ finding; never rebuild on section visit. Bake `python-docx` + `kaleido` into the Docker image (`requirements.txt`). Static Generic RCx DOCX asset may remain under `assets/reports/` via `load_generic_rcx_report` but is not an Overview download. Keep **Data Model** section + `app/data_model_tree.py`. Detail: [`vibe19_agent_spec/docs/PLOTS_DOCX_VALIDATION.md`](vibe19_agent_spec/docs/PLOTS_DOCX_VALIDATION.md). Perf findings (eager Export/coverage, Folder copies): [`vibe19_agent_spec/docs/PERF_BOTTLENECKS.md`](vibe19_agent_spec/docs/PERF_BOTTLENECKS.md). Skill: [`vibe19_agent_spec/skills/vibe19-engineering-report/SKILL.md`](vibe19_agent_spec/skills/vibe19-engineering-report/SKILL.md).

## Agent → Streamlit handoff (dialed-in URL)

Headless agents use `app/agent_api.py` / `scripts/agent_afdd.py`. After export they write:

- `out_dir/streamlit_bootstrap.json`
- `vibe_code_apps_19/.last_agent_session.json` (gitignored)

Or set `VIBE19_BOOTSTRAP=C:\path\to\streamlit_bootstrap.json` (**native Streamlit on the host**).

On Streamlit start (empty session), the app **auto-loads** that package + fault settings and optionally **re-runs all 50 rules** so Plots/RCx are ready at **http://localhost:8501**.

```powershell
python scripts/agent_afdd.py --package path\to\BUILDING_100_full_openfdd_package_v1.zip --out out_b100 --run-all
# ensure Streamlit is running (or restart it), then open http://localhost:8501
```

### GHCR / Docker bootstrap (paths must be container-visible)

- Container Streamlit listens on **internal :8501**; browse the **host** port from `-p HOST:8501` (e.g. http://localhost:8502 when `-p 8502:8501`).
- Bootstrap JSON from `agent_afdd.py` embeds **host paths**. A container **cannot** open `C:\Users\…\file.zip`.
- Bind-mount the package directory and set container paths, e.g. `package_path: "/data/package.zip"` and `VIBE19_BOOTSTRAP=/data/VIBE19_BUILDING_100_BOOTSTRAP.json`.
- Full Windows example + port-conflict notes + **pull-latest easy button**: [`docs/DOCKER.md`](docs/DOCKER.md) · root [`README.md`](README.md) Docker/GHCR · `scripts/docker_update_vibe19.(sh|ps1)`.

### Data-contract warnings (do not hide)

On package load, `app/data_contract.py` surfaces (sidebar + `package_report`):

- `quality.json` trusted_start **after** history end → would be **0 trusted rows** (history kept; never invent/backdate trust)
- `columns.csv` points absent from `history_wide.csv` → ignored for mapping (intersect only)
- `vav_to_ahu_simple.csv` mismatches; parent-AHU **quality** fallback when a VAV has no own quality / missing topology

See [`vibe19_agent_spec/DATA_CONTRACT.md`](vibe19_agent_spec/DATA_CONTRACT.md).
## Smoke-check (no browser)

```powershell
cd vibe_code_apps_19
py -3.14 scripts/smoke_streamlit_app.py
# or AppTest in pytest; or: curl http://localhost:8501/  → HTTP 200 and no exception banner
```

## HVAC / mapping context for agents

- Prefer **web OAT** (`wx_oa_t`) for weather-driven analytics and physics; BAS `oa_t` is fallback.
- **Chiller plant runtime** on weekly motor charts: designated CHW **pump status** only. No pump in the data model → **no motor series** (never fake motor hours from leave temp). Pump evidence is **not** compressor proof for OAT bins.
- **Mech-cooling OAT bins** (`app/analytics.py`): compressor devices only. Default proof = chiller/compressor status → verified cmd → amps/power; optional inferred CHW leave temp when `use_mech_cooling_status_proof` is false. Never pump-alone, `clg_valve_pct`, or CHW AHU valves. Coverage uses `eligible_no_runtime` for idle mapped compressors. Device-hours vs any-active aggregates; one running device ⇒ aggregates equal. Session key `include_ahu_chw_valve` is deprecated/ignored.
- **SCHED-1 / VAV-1 starting points** live on Overview: weekly occupancy time pickers (always → `occ_mode`) + zone comfort low/high (Units radio °F/°C; stored °F into `params["VAV-1"]`).
- Air-side weekly chart: dotted **avg OAT while on**; dashed **bare-min occupied hours/week** from the calendar.

## Agent-driven data (preprocess outside the app)

Agents prepare data **offline**, then drive the UI (or a human) to load it.

| Path | When | Spec |
| --- | --- | --- |
| Local folder | Dev machine with historian tree | [`vibe19_agent_spec/DATA_CONTRACT.md`](vibe19_agent_spec/DATA_CONTRACT.md) |
| Zip package | Streamlit Cloud / shared host / agent upload | [`docs/PACKAGE_SPEC.md`](docs/PACKAGE_SPEC.md) (`openfdd_package_v1`) |
| Multi-zip job | Browser upload of many part zips (≤500 MB each) | [`vibe19_agent_spec/docs/AGENT_CSV_PREPROCESS.md`](vibe19_agent_spec/docs/AGENT_CSV_PREPROCESS.md) |
| Agent CLI | Headless rules/analytics/RCx export | `python scripts/agent_afdd.py --package … --out … --run-all` |
| Deploy notes | `APP_MODE=auto\|cloud\|local` | [`docs/STREAMLIT_CLOUD.md`](docs/STREAMLIT_CLOUD.md) |

### Timestamp / CSV requirements (package + contract)

- Column **`timestamp_utc`** required in package CSVs (ISO-8601; UTC preferred)
- Wide CSV: one column per point; UTF-8
- Optional `columns.csv` for role hints; optional `weather/history_wide.csv` (never treated as equipment)
- Optional `session_config.json` restores units / role_map / thresholds into **session only**
- **Cloud round-trip:** upload zip → tune → **Download session config** (sidebar / Export) → later upload zip + **Upload session config** (no server path). See [`docs/STREAMLIT_CLOUD.md`](docs/STREAMLIT_CLOUD.md)
- Optional root `column_map.json` — supplement only; **each equipment CSV requires a sibling Haystack JSON** (`history_wide.json` | `history_wide.column_map.json` | `column_map.json`). Weather maps optional. Nested zips auto-expand. See [`docs/PACKAGE_SPEC.md`](docs/PACKAGE_SPEC.md).
- Zip limits (local + Cloud, env-overridable): see `docs/PACKAGE_SPEC.md`
  - **Two-tier sizes:** browser upload **500 MB** (`.streamlit/config.toml` `maxUploadSize`); agent/CLI/path **2048 MB** default (`DEFAULT_PACKAGE_MB`)
  - Prefer `scripts/agent_afdd.py --package …` or **Load zip from path** for large buildings (bypasses the Streamlit widget)
  - Override package caps: `OPENFDD_MAX_ZIP_MB`, `OPENFDD_MAX_UNCOMPRESSED_MB`, `OPENFDD_MAX_ENTRIES`, `OPENFDD_MAX_EQUIPMENT`
  - UI shows loaded dataset size (MB) vs limits in the sidebar and Overview
  - Local agents: sidebar **Package zip path** → **Load zip from path**; also **Fault settings JSON path** / **Session config JSON path**
  - Self-host Docker / GHCR: [`docs/DOCKER.md`](docs/DOCKER.md) + root **[`README.md`](README.md) Docker/GHCR** — tip `ghcr.io/bbartling/vibe19:latest`; easy button `scripts/docker_update_vibe19.(sh|ps1)` (pull + recreate). Community Cloud does **not** use the Dockerfile
  - Fork / customize (DB ingest, branding, custom faults): [`vibe19_agent_spec/docs/CUSTOMIZE.md`](vibe19_agent_spec/docs/CUSTOMIZE.md)

### Shitty / hostile CSV handling (implemented)

Zip path (`app/package_io.py`):

- Zip-slip / symlink / bomb / size / entry caps
- Pydantic `manifest.json` + `session_config.json`
- Header check: missing/`unparseable` `timestamp_utc` → `PackageError` (sidebar, no crash)
- Corrupt zip / bad JSON → `PackageError`; temp dir wiped
- Windows `Compress-Archive` backslash zips normalized (`_is_zip_dir`); extraction `OSError` → `PackageError` with rebuild hint. **Windows agents: always emit forward-slash arcnames** (Python `zipfile` + `.as_posix()`), never `Compress-Archive`

Folder path: load errors caught in sidebar; empty/invalid path does **not** wipe an existing session.

## Run

```powershell
cd vibe_code_apps_19
streamlit run streamlit_app.py
# Cloud-like: $env:APP_MODE='cloud'; streamlit run streamlit_app.py
# Headless agent:
python scripts/agent_afdd.py --package path\to\building.zip --out out_dir --run-all
# Tests (Windows-safe temp):
.\scripts\run_tests_local.ps1
```

Demo package: `python scripts/make_demo_package.py` → `data/demo_package_v1.zip`

## Regenerate configs after catalog changes

```powershell
python scripts/generate_rule_configs.py
```

## Specs

- [docs/PACKAGE_SPEC.md](docs/PACKAGE_SPEC.md) — **preprocess + timestamps for zip/Cloud**
- [docs/DATA_MODEL_DRIVEN.md](docs/DATA_MODEL_DRIVEN.md) — roles vs heuristics (chiller↔pump)
- [docs/STREAMLIT_CLOUD.md](docs/STREAMLIT_CLOUD.md)
- [docs/DOCKER.md](docs/DOCKER.md) — self-host / GHCR; pull-latest easy button (`scripts/docker_update_vibe19.*`); also root [README.md](README.md) Docker section
- [vibe19_agent_spec/docs/CUSTOMIZE.md](vibe19_agent_spec/docs/CUSTOMIZE.md) — fork: DB ingest, branding, custom faults, deploy
- [vibe19_agent_spec/DATA_CONTRACT.md](vibe19_agent_spec/DATA_CONTRACT.md) — folder tree contract
- [vibe19_agent_spec/AGENTS.md](vibe19_agent_spec/AGENTS.md)
- [vibe19_agent_spec/docs/RCX_PLOTS.md](vibe19_agent_spec/docs/RCX_PLOTS.md)
- [vibe19_agent_spec/docs/PERF_BOTTLENECKS.md](vibe19_agent_spec/docs/PERF_BOTTLENECKS.md) — Streamlit UI/data bottleneck findings
- [docs/STREAMLIT_RULE_INVENTORY.md](docs/STREAMLIT_RULE_INVENTORY.md)
- [vibe19_agent_spec/docs/OPERATIONAL_GATES.md](vibe19_agent_spec/docs/OPERATIONAL_GATES.md)
- [docs/HAYSTACK_LIKE_MAPPING_GUIDE.md](docs/HAYSTACK_LIKE_MAPPING_GUIDE.md)
