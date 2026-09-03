# Vibe 23 — Residential heat-pump DSM laboratory

Transparent EnergyPlus demand-side-management lab for a hypothetical all-electric heat-pump home:
thermal flexibility (house as battery) → finite thermostat grid search under illustrative TOU → home-battery co-optimization.

**Labels:** `HYPOTHETICAL_GL14_TUNED_DEMO_MODEL` · `ILLUSTRATIVE_RESIDENTIAL_ASSUMPTIONS` · `ILLUSTRATIVE_HIGH_VALUE_TOU_TARIFF`

> LBNL Building 59 calibration work was removed from the active path (poor whole-building DSM fit). Historical lessons under [`lessons/grid_search/`](lessons/grid_search/) remain.

## Requirements

- Windows + native EnergyPlus 26.1 at `C:\EnergyPlusV26-1-0\energyplus.exe` (override with `--eplus-path` / `ENERGYPLUS_EXE`)
- Python ≥3.12
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
| `lessons/grid_search` | Educational ExampleFiles grid-search series (Day 10 BESS) |

## Agent handoff

See [`AGENTS.md`](AGENTS.md) and [`vibe23_agent_spec/SPEC.md`](vibe23_agent_spec/SPEC.md).
