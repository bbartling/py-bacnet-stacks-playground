# Nightly A04 grid-search compute benchmark

> Grid search and RL share the same EnergyPlus model and scoring contracts, tariff accounting, and readiness criteria. RL trains on a shaped numerical reward, while grid search selects the lowest-cost fully-ready candidate.

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
- Benchmark-development EnergyPlus launches: 178
- Expected exhaustive night launches (baseline + candidates): 131
- Expected 25-policy night launches (baseline + 25): 26
- Sequential exhaustive candidate compute time (s): 320.8255178000072
- First preregistered index within 1% of exhaustive best (`n_to_within_1pct`): 1
- First preregistered index within $10 (`n_to_within_10_usd`): 1
- Identical-state proof samples: 131 (require 131); max |Δ| °F: 0.0
- 15-min target pass: True
- 30-min hard pass: True

## W2A scored-runtime warnings (appendix)

Recomputed from candidate quality artifacts (selection is comfort-readiness, not W2A=0):

- Range: 5520–8310
- Median: 6456.0
- Total across candidates: 865260

## Optional day benchmarks

- Mild weekday (`2025-12-15`): **NOT_RUN**
- Weekend (`2026-01-25`): **NOT_RUN**

## Artifacts

See CSVs/JSON in this directory (`artifact_hashes.json`, `w2a_warning_summary.json`, `identical_state_proof.json`) and `figures/` (9 PNG+SVG plots).
