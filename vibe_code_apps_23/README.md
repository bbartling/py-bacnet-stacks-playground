# Vibe 23 — Residential heat-pump DSM laboratory

Transparent EnergyPlus demand-side-management lab for a hypothetical all-electric heat-pump home:
thermal flexibility (house as battery) → finite thermostat grid search under illustrative TOU → home-battery co-optimization.

**Labels:** `HYPOTHETICAL_GL14_TUNED_DEMO_MODEL` · `ILLUSTRATIVE_RESIDENTIAL_ASSUMPTIONS` · `ILLUSTRATIVE_HIGH_VALUE_TOU_TARIFF`

> LBNL Building 59 calibration work was removed from the active path (poor whole-building DSM fit). Historical lessons under [`lessons/grid_search/`](lessons/grid_search/) remain.

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
# Windows / Linux / macOS
cd vibe_code_apps_23
python -m pip install -e ".[studio]"
copy .env.example .env   # Linux/mac: cp .env.example .env
# Edit ENERGYPLUS_EXE / ENERGYPLUS_ROOT / ENERGYPLUS_WEATHER for live EnergyPlus
streamlit run streamlit_app.py
```

Energy is charted as **kW** and **cumulative kWh**, with full-day totals from `kWh = Σ(kW × 5/60 h)`. Twin replay can coarsen the playhead to **5 / 15 / 30 / 60 min** DSM viewing levels (native fixture stays 5-min). A **static** day plot shows hourly kWh, illustrative $/hour, and outdoor dry-bulb °F (does not scrub with Play). Regenerated fixtures (diurnal lights/plugs, no ALWAYS_ON phantom): Jul-15 ≈ **28 kWh**; Jan-3 winter design-cold ≈ **245 kWh**; mild Jan-15 ≈ **41 kWh** (`winter_typical_jan15_dr_day.json`). ~**3,500 ft²** / 5-ton box.

Each browser gets a UUID session workspace under `{temp}/vibe23/{session_id}/` (Clear session wipes only that visitor). Isolation is not a password gate.

### Streamlit Community Cloud

1. Deploy from GitHub → [share.streamlit.io](https://share.streamlit.io)
2. App path: `vibe_code_apps_23/streamlit_app.py`
3. Requirements: `vibe_code_apps_23/requirements-studio.txt`
4. Cloud runs **fixture demo mode** (no native EnergyPlus). Use the in-app **Streamlit Cloud** / **Contribute** buttons.

`.env` is for local native EnergyPlus on Windows, Linux, or macOS — never commit secrets.

## Model

- [`model/residential_heat_pump_home.idf`](model/residential_heat_pump_home.idf) — Carrier 50EZ060 curves, `Timestep=12` (5-min / 288 intervals/day)
- Weather: Golden/NREL TMY3 (Denver-type) from the EnergyPlus install
- Default thermostat: 71.5°F heat / 72.5°F cool; hard envelope 69.5–74.5°F

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
| `lessons/grid_search` | Educational ExampleFiles grid-search series (Day 10 BESS) |

## Agent handoff

See [`AGENTS.md`](AGENTS.md) and [`vibe23_agent_spec/SPEC.md`](vibe23_agent_spec/SPEC.md).
