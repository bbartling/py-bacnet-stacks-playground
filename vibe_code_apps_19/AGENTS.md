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
- `app/rcx_plots.py` + `app/ui_rcx_tab.py` — multi-equipment RCx charts
- `app/weather_psychrometrics.py` — web OAT / dewpoint / wet-bulb

## Hard rules

1. **50 canonical rules** — never silently omit; use `SKIPPED_MISSING_ROLES`, `SKIPPED_EQUIPMENT_OFF`, or `NOT_APPLICABLE_EQUIPMENT_TYPE`
2. **No Rust / DataFusion / FastAPI / Flask / Haystack RDF / Oxigraph**
3. **No client historian trees in git** — local: browse folder; Cloud/shared: upload zip only (see package spec). Demo zip `data/demo_package_v1.zip` is OK
4. **Do not recreate** `haystack_rdf/`, `fdd_app/`, `fdd_dashboard_model/`
5. **Web OAT by default** for analytics / free-cool weather path
6. **`python -m pytest -q`** before done
7. **Keep `vibe19_agent_spec/` in sync** after UI/plot/rule changes (`SESSION_LOG.md`, skills, checkpoints)
8. **Bad uploads must not crash the app** — raise/catch `PackageError`, show sidebar error, wipe temp dir; never leave uncaught exceptions on zip load

## Agent-driven data (preprocess outside the app)

Agents prepare data **offline**, then drive the UI (or a human) to load it.

| Path | When | Spec |
| --- | --- | --- |
| Local folder | Dev machine with historian tree | [`vibe19_agent_spec/DATA_CONTRACT.md`](vibe19_agent_spec/DATA_CONTRACT.md) |
| Zip package | Streamlit Cloud / shared host / agent upload | [`docs/PACKAGE_SPEC.md`](docs/PACKAGE_SPEC.md) (`openfdd_package_v1`) |
| Deploy notes | `APP_MODE=auto\|cloud\|local` | [`docs/STREAMLIT_CLOUD.md`](docs/STREAMLIT_CLOUD.md) |

### Timestamp / CSV requirements (package + contract)

- Column **`timestamp_utc`** required in package CSVs (ISO-8601; UTC preferred)
- Wide CSV: one column per point; UTF-8
- Optional `columns.csv` for role hints; optional `weather/history_wide.csv` (never treated as equipment)
- Optional `session_config.json` restores units / role_map / thresholds into **session only**
- Cloud limits: ≤25 MB zip, ≤100 MB expanded, ≤50 entries, ≤20 equipment

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
