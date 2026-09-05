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
py -3.12 -m pip install -r requirements-studio.txt
# Edit ENERGYPLUS_EXE / ENERGYPLUS_ROOT / ENERGYPLUS_WEATHER for live EnergyPlus
py -3.12 -m streamlit run streamlit_app.py
```

Energy is charted as **kW** and **cumulative kWh**, with full-day totals from `kWh = Σ(kW × 5/60 h)`. Twin replay can coarsen the playhead to **5 / 15 / 30 / 60 min** DSM viewing levels (native fixture stays 5-min). Studio tabs: **Inputs** → **Grid search** (13×13 center-setpoint Q-table, live EnergyPlus with fixture fallback) → **Twin replay** (baseline or promoted winner traces) → **Grid flex calculator** (baseline vs winner flex) → **Economics**. Regenerated fixtures (diurnal lights/plugs, no ALWAYS_ON phantom): Jul-15 ≈ **28 kWh**; Jan-3 winter design-cold ≈ **245 kWh**; mild Jan-15 ≈ **41 kWh** (`winter_typical_jan15_dr_day.json`). ~**3,500 ft²** / 5-ton box.

Each browser gets a UUID session workspace under `{temp}/vibe23/{session_id}/` (Clear session wipes only that visitor). Isolation is not a password gate.

### Deployment note (Streamlit Community Cloud)

**Not supported for live EnergyPlus.** Community Cloud cannot install EnergyPlus: it is not in the Debian `packages.txt` apt set, there is no sudo for runtime installs, and the Ubuntu x86_64 tarball is ~234 MB against a ~1 GB-class container. This app is intended to run **locally** (or on a Docker host such as Hugging Face Spaces / Fly.io / Render with EnergyPlus baked into the image). Without EnergyPlus the Studio still opens in **fixture demo mode** for UI/tests — that is a fallback, not a Cloud product path.

`.env` is for local native EnergyPlus on Windows, Linux, or macOS — never commit secrets.

## Model

- [`model/residential_heat_pump_home.idf`](model/residential_heat_pump_home.idf) — Carrier 50EZ060 curves, `Timestep=12` (5-min / 288 intervals/day)
- Weather: Golden/NREL TMY3 (Denver-type) from the EnergyPlus install
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
