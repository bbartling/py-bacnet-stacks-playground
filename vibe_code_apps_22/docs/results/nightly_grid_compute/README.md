# Nightly A04 grid-search compute benchmark

> Grid search and RL share the same EnergyPlus trajectories, tariff accounting, and readiness criteria. RL trains on a shaped numerical reward, while grid search selects the lowest-cost fully-ready candidate.

## Public labels

- `SIMULATION-ONLY RESEARCH`
- `A04 IS NOT A TRANSIENT-VALIDATED PHYSICS CHAMPION`
- `VERIFIED BAS INCUMBENT REMAINS UNRESOLVED`
- `RETROSPECTIVE WEATHER BENCHMARK`
- `NOT VALIDATED FOR OPERATIONAL DSM`
- `NO BACNET COMMAND AUTHORITY`

## Verdict

**`NIGHTLY_GRID_FEASIBLE_WITHIN_15_MIN`** — recommended nightly budget: **`25`**

Primary day: `2026-01-26` (lookback `2026-01-25`).  
Weather: `RETROSPECTIVE_WEATHER_BENCHMARK`. BACnet commands: **0**.

## Key numbers

- Unique candidates evaluated: 130
- EnergyPlus launches: 178
- Exhaustive wall (s): 320.8255178000072
- Candidates within 1% of exhaustive best: 1
- Candidates within $10: 1
- 15-min target pass: True
- 30-min hard pass: True

## Artifacts

See CSVs/JSON in this directory and `figures/` (9 PNG+SVG plots).
