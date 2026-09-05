# Day 04 – Tiny Thermostat Grid (2×2)

*Vibe 23 Grid Search track | Lesson 4 of 10*

## Goal

Run your first **real** EnergyPlus grid search: four candidates on the official `5ZoneWaterLoopHeatPump.idf` example — two setbacks × two recovery leads.

## Concept

We replace the stock `HTG-SETP-SCH` compact schedule with a weekday setback → occupied heating profile, force a single January 14 run, request facility electricity + zone temperatures, then:

1. Score readiness (occupied zones ≥ 68 °F at 08:00 / 08:15)
2. Compute illustrative energy + on-peak demand dollars
3. Rank feasible plans

This is the easy on-ramp to the fuller menu in Day 05 (and the original `energyplus_grid_search_demo.py`).

## How to Use It

```bash
cd lessons/grid_search/scripts
python day04_tiny_thermostat_grid.py
```

Expect ~4 EnergyPlus runs (a few minutes total depending on hardware).

## Why This Matters

A 2×2 grid is small enough to watch every candidate print live, yet large enough to show **trade-offs**: deeper setbacks need longer recovery leads or they fail readiness.

## Mini Examples

| Candidate | Setback °F | Lead hours |
| --- | --- | --- |
| SB62_LEAD0 | 62 | 0 |
| SB62_LEAD2 | 62 | 2 |
| SB68_LEAD0 | 68 | 0 |
| SB68_LEAD2 | 68 | 2 |

Occupied heating target ≈ 70 °F (21.1 °C).

## Micro Exercises

1. Run Day 04; which candidates pass readiness?
2. Without looking at cost, predict which setback is more likely to fail with `LEAD0`.
3. Sketch how you would add a third lead time (1 h) without rewriting the parser.

## Key Takeaway

**Four EnergyPlus runs** already teach the full DSM loop. Scale the menu only after the tiny grid’s CSV makes sense.
