# Vibe Code App 19 — FDD analyst dashboard (`fdd_app`)

**Template for building your own** RCx / FDD analyst dashboard from historian CSV exports (no live BACnet). Point at any compatible data tree — swap rules, pages, and params for your site.

**Reference examples** (for developing this template, not shipped in git): `BUILDING_100`, `BUILDING_50` under your `HVAC_DATA_ROOT`.

**Agent spec (start here for vibe coding):** [`AGENTS.md`](AGENTS.md) · [`vibe19_agent_spec/TEMPLATE.md`](vibe19_agent_spec/TEMPLATE.md) · [`vibe19_agent_spec/`](vibe19_agent_spec/)

| Directory | Role |
| --- | --- |
| [`fdd_app/backend/`](fdd_app/backend/) | **Backend** — FastAPI server, pandas FDD engine, chart generation |
| [`fdd_app/frontend/`](fdd_app/frontend/) | **Frontend** — static dashboard JS/CSS |
| [`fdd_app/sidecar/`](fdd_app/sidecar/) | **Sidecar** — optional open-fdd Rust edge bridge |
| [`fdd_dashboard_model/`](fdd_dashboard_model/) | **Enhanced** — typed point catalog + VAV box loaders |
| [`shared/`](shared/) | `data_config`, validation script |

## Data (not in git)

CSV history trees are **large** (~500 MB+ with VAV) and stay **outside** the repo.

Copy [`data_paths.example.yaml`](data_paths.example.yaml) → `data_paths.local.yaml` or set:

```powershell
$env:HVAC_DATA_ROOT = "/path/to/hvac_systems_CLEANED"
$env:HVAC_BUILDING = "BUILDING_100"
```

See [`data/README.md`](data/README.md).

## Validate import

```bash
cd vibe_code_apps_19
python validate_data.py
```

## Generate dashboard (your building)

```bash
cd vibe_code_apps_19/fdd_app
pip install -r requirements-dev.txt
cd backend && python generate_dashboard.py
uvicorn asgi:app --host 127.0.0.1 --port 5000   # http://127.0.0.1:5000
```

Poll interval is read from each building’s `manifest.json` (`grid_minutes: 5` → 300s).

## Try the reference examples

```powershell
$env:HVAC_BUILDING = "BUILDING_100"   # or BUILDING_50
python generate_dashboard.py
```

## Git strategy

- **Commit:** Python, JSON mappings, docs, small example configs
- **Ignore:** `BUILDING_*`, `weather/`, `*.csv` history, generated HTML, zips, `data_paths.local.yaml`

## Status

- **Import data:** validated via `validate_data.py` when `HVAC_DATA_ROOT` is set
- **VAV terminal FDD pages:** data model scaffold in `fdd_dashboard_model/` — rules still AHU-centric in `fdd_app/backend`
