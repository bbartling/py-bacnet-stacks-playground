# Vibe 23 — Residential heat-pump DSM laboratory

Transparent EnergyPlus demand-side-management lab for a hypothetical all-electric heat-pump home:
thermal flexibility (house as battery) → finite thermostat grid search under illustrative TOU → home-battery co-optimization.

**Labels:** `HYPOTHETICAL_GL14_TUNED_DEMO_MODEL` · `ILLUSTRATIVE_RESIDENTIAL_ASSUMPTIONS` · `ILLUSTRATIVE_HIGH_VALUE_TOU_TARIFF`

> LBNL Building 59 calibration work was removed from the active path (poor whole-building DSM fit). Historical lessons under [`../lessons/grid_search/` (repo root)](../lessons/grid_search/) remain.

## Requirements

- Python ≥3.12
- Native EnergyPlus 26.1 when you want live IDF runs (optional for Streamlit fixture demo)
  - Windows: `C:\EnergyPlusV26-1-0\energyplus.exe`
  - Linux: `/usr/local/EnergyPlus-26-1-0/energyplus` (or `/opt/EnergyPlus-26-1-0`)
  - macOS: `/Applications/EnergyPlus-26-1-0/energyplus`
  - Override with `.env` (`ENERGYPLUS_EXE`, `ENERGYPLUS_ROOT`, `ENERGYPLUS_WEATHER`) or `--eplus-path`
- **No Docker / WSL required** for acceptance

## Quick start

```powershell
cd vibe_code_apps_23
python -m pip install -e ".[dev]"

vibe23 residential-doctor
vibe23 residential-smoke --season jul
vibe23 residential-smoke --season jan
vibe23 residential-dr --season summer
vibe23 residential-grid --season summer --max-candidates 3
vibe23 residential-grid --season winter --max-candidates 3
vibe23 residential-battery-grid --season summer --max-candidates 2
vibe23 residential-report
```

## Streamlit studio

Interactive twin replay (24h in ~60s), Plotly IDF massing, battery sizing, summer **and** winter extreme days, IDF/EPW/tariff uploads, hourly weather+price spreadsheet editor, light Streamlit default theme (same feel as vibe 19–22), and energy-modeler dashboard:

```powershell
# Windows — preferred launcher (Python 3.12 + Streamlit 1.59.2 pin)
cd vibe_code_apps_23
py -3.12 -m pip install -e ".[studio]"
copy .env.example .env
.\scripts\run_studio.ps1
# Hard-refresh the browser once (Ctrl+Shift+R) after switching interpreters.
```

Or manually:

```powershell
cd vibe_code_apps_23
py -3.12 -m pip install -r requirements.txt   # studio pins + editable vibe23
# Edit ENERGYPLUS_EXE / ENERGYPLUS_ROOT / ENERGYPLUS_WEATHER for live EnergyPlus
py -3.12 -m streamlit run streamlit_app.py
```

[`requirements.txt`](requirements.txt) exists so hosts that only look for that filename pick
up the studio dependency set; it pulls in [`requirements-studio.txt`](requirements-studio.txt)
plus an editable install of this package (the app imports `vibe23`). Run it with
`vibe_code_apps_23` as the working directory so `-e .` resolves.

**EnergyPlus is not a Python package.** Putting it in `requirements.txt` does nothing useful —
that file only installs pip deps. Live runs need a **full native EnergyPlus 26.1 distribution**
(executable + `Energy+.idd` + `ExpandObjects` + bundled libs/weather), because the runner invokes
`energyplus -x -w … -d … -r in.idf`. Copying only the `energyplus` binary is insufficient.

Energy is charted as **kW** and **cumulative kWh**, with full-day totals from `kWh = Σ(kW × 5/60 h)`. Twin replay can coarsen the playhead to **5 / 15 / 30 / 60 min** DSM viewing levels (native fixture stays 5-min). Studio tabs: **Inputs** → **Grid search** (13×13 center-setpoint Q-table, live EnergyPlus with fixture fallback) → **Twin replay** (baseline or promoted winner traces) → **Grid flex calculator** (baseline vs winner flex) → **Economics**. Regenerated fixtures (diurnal lights/plugs, no ALWAYS_ON phantom): Jul-15 ≈ **28 kWh**; Jan-3 winter design-cold ≈ **245 kWh**; mild Jan-15 ≈ **41 kWh** (`winter_typical_jan15_dr_day.json`). ~**3,500 ft²** / 5-ton box.

Each browser gets a UUID session workspace under `{temp}/vibe23/{session_id}/` (Clear session wipes only that visitor). Isolation is not a password gate.

### Deploy on Streamlit Community Cloud (with Render EnergyPlus worker)

Studio is **Render-worker only** for live sims (no native EnergyPlus on Cloud). Frontend = Streamlit.io; physics = [vibe23-energyplus-worker](https://github.com/bbartling/vibe23-energyplus-worker) on [Render](https://vibe23-energyplus-worker.onrender.com/).

1. Merge/push `vibe_code_apps_23` on GitHub (`develop` or your deploy branch).
2. [share.streamlit.io](https://share.streamlit.io/) → **New app** → this repo → set:
   - **Main file path:** `vibe_code_apps_23/streamlit_app.py`
   - **Python version:** 3.12
3. **App settings → Secrets** (TOML):

```toml
EPLUS_BACKEND = "worker"
EPLUS_WORKER_URL = "https://vibe23-energyplus-worker.onrender.com"
EPLUS_WORKER_API_KEY = "same-as-Render-service-API_KEY"
```

4. Deploy. Open the app → sidebar **EnergyPlus worker** → confirm stoplight → **Wake worker** if red (free tier sleeps; ~30–90s).
5. On **Inputs**, click **Load package residential demo IDF** (assets ship in-repo under `src/vibe23/assets/`; if missing, Studio downloads them from GitHub `develop` automatically).
6. Set catalog size to **5** (smoke), run Campaign; only then try **169** on a paid/always-on worker.

Worker docs: [Swagger `/docs`](https://vibe23-energyplus-worker.onrender.com/docs) · [healthz](https://vibe23-energyplus-worker.onrender.com/healthz) · [source](https://github.com/bbartling/vibe23-energyplus-worker). Job queue: `GET /v1/jobs` (Bearer) — Streamlit sidebar **Worker job queue**.

Native EnergyPlus cannot be installed via `requirements.txt` on Community Cloud; keep sims on the worker. Free Render sleep + CPU limits make large 169-cell campaigns slow or fragile — use a small catalog first or a paid always-on instance.

`.env` / `.env.local` are for local keys only — never commit secrets.

### Committed proxy fixtures are not shown in Studio

On-disk `fixtures/studio/*_thermostat_grid_ranking.json` / `*_twin_export.json` may still exist for offline unit tests and carry `fixture_kind: "ILLUSTRATIVE_PHYSICS_PROXY"`. **Studio never loads them into Grid search / Twin / Flex.** Those tabs require a live EnergyPlus session ranking (`ranking.json` / `twin_export.json` written by **Run live EnergyPlus search**).

### Ranking acceptance

A candidate is only rankable when its EnergyPlus run passes the **strict** gate `ok` (return code 0, zero fatals, **zero severes**, CSV present) — not the permissive `soft_ok`, which tolerates severes. Non-`ok` rows are stored with `billing_cost = inf` and both flags kept for transparency. Battery scoring uses `restore_final_soc=True`, so no candidate can win by ending the day with a drained battery.

## Model

- [`src/vibe23/assets/residential_heat_pump_home.idf`](src/vibe23/assets/residential_heat_pump_home.idf) — Carrier 50EZ060 curves, `Timestep=12` (5-min / 288 intervals/day); mirrored under [`model/`](model/)
- Weather: Golden/NREL TMY3 packaged next to the IDF in `src/vibe23/assets/`
- Default thermostat: **71°F heat / 73°F cool** (2°F deadband around center **72°F**); hard envelope 69.5–74.5°F
- Grid flex search: **13×13 = 169** center setpoints (69.0…75.0 @ 0.5°F) with fixed TOU event hours; ranking is **battery-co-optimized** purchased-grid $/day

## Package map

| Module | Role |
|--------|------|
| `vibe23.residential` | IDF paths, thermostat schedules, DR, campaigns |
| `vibe23.grid` | Deterministic finite grid enumeration |
| `vibe23.tariff` / `residential.tariffs` | Evidence-gated tariffs; 288-interval TOU fixtures |
| `vibe23.battery` | Behind-the-meter SOC dispatch |
| `vibe23.compute` | Host + campaign compute telemetry |
| `vibe23.weather` | `WeatherProvider` (static EPW + forecast fixtures) |
| `vibe23.studio` | Streamlit helpers: IDF massing, demo day, kWh integration |
| `../lessons/grid_search` | Educational ExampleFiles grid-search series (Day 10 BESS) |

## Agent handoff

See [`AGENTS.md`](AGENTS.md) and [`vibe23_agent_spec/SPEC.md`](vibe23_agent_spec/SPEC.md).
