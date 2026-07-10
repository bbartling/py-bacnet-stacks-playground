# Agent prompt — Streamlit 50-rule pandas FDD demo

**Open-FDD (Rust/DataFusion):** `C:\Users\ben\Documents\open-fdd` — do **not** re-add Rust here.

Codex / Claude / Cursor: paste this file as the session brief. For **Cloud zip preprocess**, also read [`docs/PACKAGE_SPEC.md`](docs/PACKAGE_SPEC.md).

## Mission

Maintain Vibe App 19 as an **educational Streamlit demo** with the **full 50-rule pandas cookbook**:

- `app/rules/cookbook_catalog.py` — rule definitions
- `app/rules/runner.py` — skip / equipment-off / not-applicable execution
- `configs/rule_inventory.yaml` + `rule_defaults.yaml`
- `streamlit_app.py` — unified **Folder | Zip** picker, Overview, mapping, run rules, **Plots**, **RCx Plots**, analytics
- `app/package_io.py` — safe `openfdd_package_v1` zip ingest (Cloud + local)
- `app/agent_api.py` + `scripts/agent_afdd.py` — **Streamlit-free** agent load / run / export
- `app/weather_resolver.py` — web OAT primary / BAS fallback / OAT-METEO both-required
- `app/rcx_plots.py` + `app/ui_rcx_tab.py` — multi-equipment RCx charts
- `app/weather_psychrometrics.py` — web OAT / dewpoint / wet-bulb

## Hard rules

1. **50 canonical rules** — never silently omit; use `SKIPPED_MISSING_ROLES`, `SKIPPED_EQUIPMENT_OFF`, or `NOT_APPLICABLE_EQUIPMENT_TYPE`
2. **No Rust / DataFusion / FastAPI / Flask / Haystack RDF / Oxigraph**
3. **No client historian trees in git** — local: browse folder; Cloud/shared: upload zip only (see package spec). Demo zip `data/demo_package_v1.zip` is OK
4. **Do not recreate** `haystack_rdf/`, `fdd_app/`, `fdd_dashboard_model/`
5. **Web OAT by default** for analytics / free-cool / physics rules needing OAT (`oa_t_effective`); OAT-METEO compares BAS vs web **only when both exist**
6. **`python -m pytest -q`** before done (Windows locked temp: `scripts/run_tests_local.ps1`)
7. **Keep `vibe19_agent_spec/` in sync** after UI/plot/rule changes (`SESSION_LOG.md`, skills, checkpoints)
8. **Bad uploads must not crash the app** — raise/catch `PackageError`, show sidebar error, wipe temp dir; never leave uncaught exceptions on zip load
9. **Agent API is importable Python only** — `app/agent_api.py` (+ optional CLI). No HTTP API / background server.
10. **Runtime proof = motor/status first** — chiller weekly + mech-cooling OAT bins use designated `chw_pump_status` / `chw_pump_cmd` (or DX compressor on AHU/HP). If the data model has **no pump to map**, **omit** that chiller from run-hours charts — do **not** invent runtime from CHW leave/supply temp.
11. **Mech-cooling OAT bins = compressors / plant only** — map chillers as chillers; if an AHU has DX/compressor stages, that counts as the cooling machine. **Do not** put CHW cooling-valve % on this chart (controls techs: valves often modulate with no chilled water → noisy false “cooling”). Bins must sort cold→hot by `bin_start`.

## Agent → Streamlit handoff (dialed-in URL)

Headless agents use `app/agent_api.py` / `scripts/agent_afdd.py`. After export they write:

- `out_dir/streamlit_bootstrap.json`
- `vibe_code_apps_19/.last_agent_session.json` (gitignored)

Or set `VIBE19_BOOTSTRAP=C:\path\to\streamlit_bootstrap.json`.

On Streamlit start (empty session), the app **auto-loads** that package + fault settings and optionally **re-runs all 50 rules** so Plots/RCx are ready at **http://localhost:8501**.

```powershell
python scripts/agent_afdd.py --package path\to\BUILDING_100_full_openfdd_package_v1.zip --out out_b100 --run-all
# ensure Streamlit is running (or restart it), then open http://localhost:8501
```

## Smoke-check (no browser)

```powershell
cd vibe_code_apps_19
py -3.14 scripts/smoke_streamlit_app.py
# or AppTest in pytest; or: curl http://localhost:8501/  → HTTP 200 and no exception banner
```

## HVAC / mapping context for agents

- Prefer **web OAT** (`wx_oa_t`) for weather-driven analytics and physics; BAS `oa_t` is fallback.
- **Chiller plant runtime** on weekly motor charts: designated CHW **pump status** only. No pump in the data model → **no series** (never fake hours from leave temp).
- **SCHED-1 / VAV-1 starting points** live on Overview: weekly occupancy time pickers + zone comfort low/high °F (pushed into `params["VAV-1"]`).
- Air-side weekly chart: dotted **avg OAT while on**; dashed **bare-min occupied hours/week** from the calendar.

## Agent-driven data (preprocess outside the app)

Agents prepare data **offline**, then drive the UI (or a human) to load it.

| Path | When | Spec |
| --- | --- | --- |
| Local folder | Dev machine with historian tree | [`vibe19_agent_spec/DATA_CONTRACT.md`](vibe19_agent_spec/DATA_CONTRACT.md) |
| Zip package | Streamlit Cloud / shared host / agent upload | [`docs/PACKAGE_SPEC.md`](docs/PACKAGE_SPEC.md) (`openfdd_package_v1`) |
| Agent CLI | Headless rules/analytics/RCx export | `python scripts/agent_afdd.py --package … --out … --run-all` |
| Deploy notes | `APP_MODE=auto\|cloud\|local` | [`docs/STREAMLIT_CLOUD.md`](docs/STREAMLIT_CLOUD.md) |

### Timestamp / CSV requirements (package + contract)

- Column **`timestamp_utc`** required in package CSVs (ISO-8601; UTC preferred)
- Wide CSV: one column per point; UTF-8
- Optional `columns.csv` for role hints; optional `weather/history_wide.csv` (never treated as equipment)
- Optional `session_config.json` restores units / role_map / thresholds into **session only**
- Optional `column_map.json` — loaded into `PackageLoadResult`, validated, merged into role_map
- Zip limits (local + Cloud, env-overridable): see `docs/PACKAGE_SPEC.md`
  - Defaults: local/auto **1024 MB** zip / **1024 MB** expanded / **200** entries / **100** equipment
  - `APP_MODE=cloud` default zip **250 MB**; override with `OPENFDD_MAX_ZIP_MB`, `OPENFDD_MAX_UNCOMPRESSED_MB`, `OPENFDD_MAX_ENTRIES`, `OPENFDD_MAX_EQUIPMENT`
  - Local agents: sidebar **Package zip path** → **Load zip from path**; also **Fault settings JSON path** / **Session config JSON path**

### Shitty / hostile CSV handling (implemented)

Zip path (`app/package_io.py`):

- Zip-slip / symlink / bomb / size / entry caps
- Pydantic `manifest.json` + `session_config.json`
- Header check: missing/`unparseable` `timestamp_utc` → `PackageError` (sidebar, no crash)
- Corrupt zip / bad JSON → `PackageError`; temp dir wiped

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
- [vibe19_agent_spec/DATA_CONTRACT.md](vibe19_agent_spec/DATA_CONTRACT.md) — folder tree contract
- [vibe19_agent_spec/AGENTS.md](vibe19_agent_spec/AGENTS.md)
- [vibe19_agent_spec/docs/RCX_PLOTS.md](vibe19_agent_spec/docs/RCX_PLOTS.md)
- [docs/STREAMLIT_RULE_INVENTORY.md](docs/STREAMLIT_RULE_INVENTORY.md)
- [vibe19_agent_spec/docs/OPERATIONAL_GATES.md](vibe19_agent_spec/docs/OPERATIONAL_GATES.md)
- [docs/HAYSTACK_LIKE_MAPPING_GUIDE.md](docs/HAYSTACK_LIKE_MAPPING_GUIDE.md)
