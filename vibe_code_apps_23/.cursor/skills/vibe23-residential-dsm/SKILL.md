---
name: vibe23-residential-dsm
description: >-
  Run Vibe 23 residential heat-pump EnergyPlus DSM workflows (doctor, smoke,
  DR, 13x13 thermostat center grid, battery co-opt, Grid flex Studio) on native
  Windows EnergyPlus. Use when editing vibe_code_apps_23 residential modules,
  IDF, tariffs, or campaigns.
---

# Vibe 23 residential DSM

## Constraints
- Label model `HYPOTHETICAL_GL14_TUNED_DEMO_MODEL` — never fabricate GL14 metrics
- Native `C:\EnergyPlusV26-1-0\energyplus.exe`; Docker/WSL not acceptance gates
- `Timestep=12` → 288 intervals/day; generalize tariff/reward interval counts
- Default thermostat **71/73°F** (2°F deadband around 72°F); grid search **13×13 = 169** centers
- Ranking objective: battery-co-optimized purchased-grid $/day (comfort FAIL band gated)
- Studio tabs: Inputs | Grid search | Twin replay | Grid flex calculator | Economics
- Preserve repo-root `lessons/grid_search/` (Day 10 BESS); do not resurrect B59 calibration
- Optional MCP: `C:\Users\ben\OneDrive\Desktop\testing\EnergyPlus-MCP`

## CLI
```powershell
vibe23 residential-doctor
vibe23 residential-smoke --season jul|jan
vibe23 residential-dr --season summer
vibe23 residential-grid --season summer|winter --max-candidates N
vibe23 residential-battery-grid --season summer|winter
vibe23 residential-report
```

## Loop
Edit → native EnergyPlus → read `.err` → pytest → next milestone.
