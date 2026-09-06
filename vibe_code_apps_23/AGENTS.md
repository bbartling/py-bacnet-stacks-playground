# AGENTS.md — Vibe 23 residential heat-pump DSM

**Mission:** run a transparent residential EnergyPlus DSM lab (Grid flex calculator → thermostat center search → battery co-opt) on the **Render EnergyPlus worker**. Studio UI is Render-only.

**Claim boundary:** `HYPOTHETICAL_GL14_TUNED_DEMO_MODEL`. Never fabricate Guideline 14 NMBE/CV(RMSE). Tariffs are `ILLUSTRATIVE_HIGH_VALUE_TOU_TARIFF`.

## Where the demo files live (humans)

| Asset | Path in this package |
|---|---|
| Residential demo IDF | [`src/vibe23/assets/residential_heat_pump_home.idf`](src/vibe23/assets/residential_heat_pump_home.idf) (mirrored under [`model/`](model/)) |
| Golden/NREL TMY3 EPW | [`src/vibe23/assets/USA_CO_Golden-NREL.724666_TMY3.epw`](src/vibe23/assets/USA_CO_Golden-NREL.724666_TMY3.epw) |
| Model notes | [`model/README.md`](model/README.md) |
| Studio app | [`streamlit_app.py`](streamlit_app.py) |
| Render worker | https://vibe23-energyplus-worker.onrender.com/ |
| Worker Swagger UI | https://vibe23-energyplus-worker.onrender.com/docs |

Demo days: **Jul 15** (summer TOU) and **Jan 3** (winter design cold), both from the Golden EPW.

## Mandatory reading
1. This file
2. [`README.md`](README.md)
3. [`vibe23_agent_spec/SPEC.md`](vibe23_agent_spec/SPEC.md)
4. [`model/README.md`](model/README.md)
5. [`../lessons/grid_search/INDEX.md`](../lessons/grid_search/INDEX.md) (preserve Day 10 BESS ideas)

## Hard rules
- Studio live sims are locked to the [Render EnergyPlus worker](https://vibe23-energyplus-worker.onrender.com/) (`EPLUS_BACKEND=worker` + `EPLUS_WORKER_URL` + `EPLUS_WORKER_API_KEY`). Do not surface local `ENERGYPLUS_EXE` / install paths in the Studio UI. Point humans at [Swagger `/docs`](https://vibe23-energyplus-worker.onrender.com/docs) (Authorize with the same bearer key). Studio uses **per-browser session workspaces** (`session_id` under temp `vibe23/…`) — isolation for multi-user Cloud, not a login wall; **Clear session** rotates the id.
- Do not resurrect LBNL B59 calibration as the active product
- Do not duplicate grid-search engines; reuse `vibe23.grid`
- Default thermostat is **71/73°F** (2°F deadband); full catalog is **13×13 centers** (169). Sidebar **Render catalog size** can truncate (default 5) for smoke; 169 = full search.
- Allowable zone temp drift sliders are unit-aware (°F/°C display); scoring stores °F.
- **Ranking acceptance is `metrics["ok"]`, not `soft_ok`**: a candidate is only scored when EnergyPlus returned 0 with zero fatals **and zero severes**. `soft_ok` tolerates severes and must never gate a rank. Store both flags on rows; non-`ok` rows get `billing_cost = inf`
- **Greedy battery scoring uses `restore_final_soc=True`** (`vibe23.battery.simulate_dispatch`), closing the day back to `initial_soc` so no candidate wins by draining stored energy it never bought. Do not remove this from `campaign._score_kw` or from the fixture generator
- `parse_eplus_csv` accepts **exactly 288 rows** and raises otherwise (hourly output would mis-scale kW by 12×). Never pad or truncate to make a run parse
- Committed `fixtures/studio/*_ranking.json` / `*_twin_export.json` are `ILLUSTRATIVE_PHYSICS_PROXY` — synthetic, no EnergyPlus. Never present them as simulations; see [`model/README.md`](model/README.md) for model simplifications
- Studio tabs: **Inputs** (IDF/EPW/tariff + static massing) | **Campaign** (sidebar catalog or full 169 + search heatmap) | **Grid flex** (day replay + baseline vs winner) | **Economics**. Live sims are locked to the [Render EnergyPlus worker](https://vibe23-energyplus-worker.onrender.com/). No synthetic proxy rankings in Flex.
- Tariff/reward interval count is configurable (288 for 5-min residential)
- Record compute telemetry for campaigns (`reports/compute/`, campaign `compute/`)
- After IDF edits: run EnergyPlus (Render or local CLI), read `.err`, then tests

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
`C:\Users\ben\OneDrive\Desktop\testing\EnergyPlus-MCP` may help inspect objects; it is **not** a runtime dependency for Studio.
