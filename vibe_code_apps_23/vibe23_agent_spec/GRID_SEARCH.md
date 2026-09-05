# Grid search — residential

Reuse `vibe23.grid.enumerate_grid` / `run_grid_search` contracts.

Residential campaigns in `vibe23.residential.campaign`:
- Enumerate thermostat action dimensions
- Patch IDF setpoint schedules at 5-minute resolution
- Score with `billing_cost` on 288-interval facility kW
- Reject comfort violations (outside 69.5–74.5°F)
- Write `ranking.csv`, `winner_schedule.json`, compute telemetry

Lessons under `../lessons/grid_search/` (repo root) remain educational ExampleFiles tutorials.
