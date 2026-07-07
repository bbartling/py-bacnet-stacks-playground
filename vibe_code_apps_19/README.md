# Vibe Code App 19 — CSV FDD dashboards

Building **50** and **100** fault-detection dashboards from hardcoded CSV exports (no live BACnet). Two siblings share one external data root:

**Agent spec (start here for vibe coding):** [`AGENTS.md`](AGENTS.md) · [`vibe19_agent_spec/`](vibe19_agent_spec/)

| Directory | Role |
| --- | --- |
| [`csv_fdd_dashboard/`](csv_fdd_dashboard/) | **Simple** — ported Plotly HTML generator + Flask tune/deploy (from `building100_dashboard`) |
| [`fdd_dashboard_model/`](fdd_dashboard_model/) | **Enhanced** — typed point catalog + VAV box loaders for terminal-level rules |
| [`shared/`](shared/) | `data_config`, validation script |

## Data (not in git)

Refreshed client import (~528 MB, 5-min grid, 88 VAV folders):

`C:\Users\ben\OneDrive\Desktop\testing\tadco_openfdd_sidecar\workspace\imports\hvac_systems_CLEANED`

Copy [`data_paths.example.yaml`](data_paths.example.yaml) → `data_paths.local.yaml` or set:

```powershell
$env:HVAC_DATA_ROOT = "C:\Users\ben\OneDrive\Desktop\testing\tadco_openfdd_sidecar\workspace\imports\hvac_systems_CLEANED"
$env:HVAC_BUILDING = "BUILDING_100"
```

See [`data/README.md`](data/README.md).

## Validate import

```bash
cd vibe_code_apps_19
python -m shared.validate_hvac_data
```

## Generate dashboard (Building 100)

```bash
cd vibe_code_apps_19/csv_fdd_dashboard
pip install -r requirements-dev.txt
python generate_dashboard.py
python app.py   # interactive tuning at http://127.0.0.1:5000
```

Poll interval is read from each building’s `manifest.json` (`grid_minutes: 5` → 300s).

## Switch buildings

```powershell
$env:HVAC_BUILDING = "BUILDING_50"
python generate_dashboard.py
```

Building 50 uses the same code path; VAV metadata on 2/45 boxes has a known bad `point_name` prefix in the import — see validation warnings.

## Git strategy

- **Commit:** Python, JSON mappings, docs, small example configs
- **Ignore:** `BUILDING_*`, `weather/`, `*.csv` history, generated HTML, zips, `data_paths.local.yaml`

## Status

- **Import data:** GO after `poll_seconds` wired (done in this app)
- **VAV terminal FDD pages:** data present; rules still AHU-centric in `csv_fdd_dashboard` — use `fdd_dashboard_model` next
