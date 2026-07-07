# CSV FDD dashboard (Building 100 / 50)

Multi-page HTML dashboard for zone comfort, economizer/free-cooling diagnostics, weather validation, and central plant analytics. Part of **[vibe_code_apps_19](../README.md)** — data comes from an external CSV tree via [`shared/data_config.py`](../shared/data_config.py) (`HVAC_DATA_ROOT` or `../data_paths.local.yaml`).

## Project layout (Unity WebGL-style)

| Folder / file | Role |
|---------------|------|
| `site/` | **Pre-built charts** (like a WebGL Build) — generated, not committed |
| `app.py` | Flask app — `full` mode locally, `deploy` mode on PythonAnywhere |
| `wsgi.py` | PythonAnywhere WSGI entry |
| `build_pa_deploy.py` | Builds `building100_pa_deploy.zip` for upload |
| `generate_dashboard.py` | Source generator (local dev only) |
| `data/analyst_notes.json` | Live notes on PA (runtime, gitignored) |

## Quick start — local analyst (tune + notes)

```bash
cd vibe_code_apps_19/csv_fdd_dashboard
pip install -r requirements-dev.txt
python app.py
```

Open **http://127.0.0.1:5000/index.html** — sliders, refresh, notes, export zip.

## PythonAnywhere deploy (read-only charts + notes)

```bash
pip install -r requirements-dev.txt
python build_pa_deploy.py --from-session
```

Upload **`building100_pa_deploy.zip`** → extract on PA → configure `wsgi.py` → Reload.

Full steps: **[PYTHONANYWHERE.md](PYTHONANYWHERE.md)**

- **Public / client:** set `ANALYST_ENABLED=0` — view-only charts with baked-in notes
- **You (analyst):** set `ANALYST_ENABLED=1` — edit notes on live site (charts update only when you rebuild zip locally)

## Git

```bash
cd vibe_code_apps_19/csv_fdd_dashboard
git init
git add .
git commit -m "Initial dashboard project"
```

`.gitignore` excludes generated HTML, `site/`, zips, session files, and CSV exports. Source `.py`, docs, and configs are tracked.

## Quick start (static only, no Flask)

From the **project root** (`hvac_systems_CLEANED`):

```bash
python -m http.server 8000
```

Open in your browser:

**http://localhost:8000/building100_dashboard/index.html**

## Interactive analyst mode (Flask)

Tune fault thresholds per page, add analyst notes, and export a client-ready package:

```bash
cd vibe_code_apps_19/csv_fdd_dashboard
pip install -r requirements-dev.txt
python app.py
```

Open **http://127.0.0.1:5000/index.html**

Each page has:
- **Sliders + number inputs** for fault parameters relevant to that page
- **Refresh this page** — recomputes charts with new thresholds (~15 s)
- **Notes** — per-page text saved in `analyst_session.json`
- **Export client package** — sanitized read-only zip (`building100_dashboard_readonly.zip`) for Google Drive, local re-run, or cloud static hosting — see `DEPLOY.md` inside the package

### Package for Drive / cloud (CLI)

After tuning in Flask (or with defaults):

```bash
cd vibe_code_apps_19/csv_fdd_dashboard
python package_dashboard.py --from-session   # uses saved tuning + notes
# or
python package_dashboard.py                  # default parameters
```

Output:
- `client_package/` — unzipped folder ready to deploy
- `building100_dashboard_readonly.zip` — upload to Google Drive

**Recipients:** download, unzip, double-click `serve.bat` (or `./serve.sh`), open http://localhost:8000/index.html

**Cloud (read-only):** upload unzipped folder to Netlify Drop, Cloudflare Pages, GitHub Pages, Google Cloud Storage static site, etc. Full instructions in `DEPLOY.md`.

The package is **sanitized** — no Python source, no Flask, no raw BAS history, no analyst session files. Charts and CSV summaries only.

## Regenerate reports

After updating CSV data under `BUILDING_100/` or `weather/`:

```bash
cd vibe_code_apps_19/csv_fdd_dashboard
python generate_dashboard.py
```

Tunable defaults live in `fault_tune_defaults.json` (generated on each run).

## Pages

| Page | Contents |
|------|----------|
| `index.html` | Overview KPIs and links to all reports |
| `zones.html` | Floor-level 72°F comfort, monthly zone temps, worst VAV rankings by season |
| `weather.html` | AHU 1 & 2 BAS OAT vs Open-Meteo with ±5°F fault overlay |
| `ahu_1.html` / `ahu_2.html` | AHU trends (SAT/MAT/OAT/RAT, MAD, CHW, economizer) with fault flags |
| `economizer.html` | FC8–FC13 economizer and free-cooling fault hours by season |
| `economizer_diagnostics.html` | **AHU economizer FDD** — point mapping, fault cards, trend plots, CSV export |
| `central_plant.html` | Chiller 1 & 2, boilers/pumps with fault overlays |
| `excess_runtime.html` | Weekly fan runtime outside lease hours when zones are 70–75°F |

## Assumptions

- **Occupied:** Mon–Fri 6:00–17:00, Sat 7:00–14:00, Sun closed (America/Chicago)
- **Comfort target:** 72°F ±2°F (70–74°F) during occupied hours
- **Seasons:** Heating tail Mar 16–31, Spring economizer Apr–May, Mech cooling Jun–Jul 3
- **Weather fault:** BAS OAT vs Open-Meteo dry bulb, fault when \|Δ\| > 5°F

## Data limitation

The export includes zone space temperatures and AHU/plant points, but **not** individual VAV airflow, damper command, or reheat valve histories. VAV damper/hunting/leaking rules require those points.

## Economizer FDD module

Production-grade economizer diagnostics (`economizer_fdd_engine.py`) with:

- Point mapping schema: `economizer_point_mapping.json`
- Research summary: `docs/ECONOMIZER_FDD_RESEARCH.md`
- Operator guide: `docs/ECONOMIZER_FDD_OPERATOR_GUIDE.md`
- DataFusion SQL templates: `docs/economizer_fdd_rules.sql`
- Unit tests: `pytest test_economizer_diagnostics.py` and `pytest test_sensor_qa.py`
- Sensor QA reference: `docs/SENSOR_QA_REFERENCE.md`
- Config: `sensor_fault_defaults.json` (hard ranges + ROC imperial/metric)

Exports: `economizer_diagnostics_summary_*.csv`, `economizer_fault_timeseries_ahu_*.csv`, `sensor_limits_reference.csv`

## Files

- `generate_dashboard.py` — report generator (pandas + plotly)
- `dashboard_server.py` — Flask app for tuning, notes, and client export
- `dashboard_params.py` — tunable fault parameter schema
- `fault_tune_defaults.json` — default tune values (auto-generated)
- `package_dashboard.py` — sanitized read-only package builder (Drive / cloud deploy)
- `economizer_fdd_engine.py` — AHU economizer FDD rules engine
- `economizer_diagnostics_page.py` — dedicated diagnostics HTML builder
- `plotly.min.js` — shared Plotly bundle (offline-capable)
- `zone_comfort_by_season.csv` / `floor_comfort_by_season.csv` — exported summaries
