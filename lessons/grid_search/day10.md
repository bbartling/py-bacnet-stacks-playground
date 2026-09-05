# Day 10 – BESS Bonus (PV + Battery Grid Search)

*Vibe 23 Grid Search track | Lesson 10 of 10*

## Goal

Finish the track with an electrical storage (BESS) search on the stock `ShopWithPVandBattery.idf` example: vary **SOC window** and **pack size**, then rank candidates by **purchased** electricity + on-peak demand.

## Concept

HVAC setpoints are not the only DSM actuators. Behind-the-meter PV + battery models expose:

- `ElectricLoadCenter:Distribution` — max/min SOC fractions, storage operation scheme
- `ElectricLoadCenter:Storage:Battery` — module count, initial SOC, electrical limits

Day 10 patches those fields across a five-candidate menu and scores the utility-facing meter (`ElectricityPurchased:Facility` when present).

## How to Use It

```bash
cd lessons/grid_search/scripts
python day10_bess_battery.py
```

Summer day (July 15) so PV production interacts with storage. Outputs include battery charge-state variables for optional plotting.

## Why This Matters

Grid-interactive buildings increasingly co-optimize **thermal** and **electrical** flexibility. A transparent BESS menu keeps the same educational contract: finite candidates, CSV ranking, no BAS writes.

## Mini Examples

| Candidate | Idea |
| --- | --- |
| `BASE_SOC95_20_P10` | Stock-like SOC 0.95/0.20, 10 modules parallel |
| `DEEP_SOC90_10_P10` | Wider usable SOC band |
| `SHALLOW_SOC80_40_P10` | Narrow band (protect battery) |
| `BIGGER_PACK_P15` | More parallel modules |
| `SMALLER_PACK_P5` | Fewer parallel modules |

## Micro Exercises

1. Run Day 10; which pack/SOC policy minimizes purchased kWh?
2. Does the biggest pack always win peak demand? Inspect the CSV.
3. Bonus: open `ShopWithPVandLiIonBattery.idf` and list how its storage object type differs from `ElectricLoadCenter:Storage:Battery`.

## Key Takeaway

**BESS grid search is the same loop** as thermostat DSM — swap the actuator fields, keep readiness/quality gates and an honest, simple objective. Educational only; not a bankable storage dispatch tool.
