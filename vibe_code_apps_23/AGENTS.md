# AGENTS.md — Vibe 23 residential heat-pump DSM

**Mission:** run a transparent residential EnergyPlus DSM lab (DR → thermostat grid → battery) on native Windows EnergyPlus 26.1.

**Claim boundary:** `HYPOTHETICAL_GL14_TUNED_DEMO_MODEL`. Never fabricate Guideline 14 NMBE/CV(RMSE). Tariffs are `ILLUSTRATIVE_HIGH_VALUE_TOU_TARIFF`.

## Mandatory reading
1. This file
2. [`README.md`](README.md)
3. [`vibe23_agent_spec/SPEC.md`](vibe23_agent_spec/SPEC.md)
4. [`model/README.md`](model/README.md)
5. [`../lessons/grid_search/INDEX.md`](../lessons/grid_search/INDEX.md) (preserve Day 10 BESS ideas)

## Hard rules
- Native `C:\EnergyPlusV26-1-0\energyplus.exe` is the acceptance path; Docker/WSL/MCP are optional helpers only
- Do not resurrect LBNL B59 calibration as the active product
- Do not duplicate grid-search engines; reuse `vibe23.grid`
- Tariff/reward interval count is configurable (288 for 5-min residential)
- Record compute telemetry for campaigns (`reports/compute/`, campaign `compute/`)
- After IDF edits: run EnergyPlus, read `.err`, then tests

## Resume commands
```powershell
cd vibe_code_apps_23
pip install -e ".[dev]"
vibe23 residential-doctor
vibe23 residential-smoke --season jul
python -m pytest
python -m ruff check src tests
```

## Optional EnergyPlus MCP
`C:\Users\ben\OneDrive\Desktop\testing\EnergyPlus-MCP` may help inspect objects; it is **not** a runtime dependency.
