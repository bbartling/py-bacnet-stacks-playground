# Day 02 – Fake-Data Grid Search (Stdlib Toy Model)

*Vibe 23 Grid Search track | Lesson 2 of 10*

## Goal

Run a complete forecast → menu → simulate → readiness → rank loop using **only the Python standard library** and a six-zone toy thermal model. No EnergyPlus yet.

## Concept

The companion script is a teaching twin of the Vibe22 workflow shape. It invents a brutally cold January forecast, builds a bounded menu (setback × lead × extension), simulates 96 fifteen-minute steps, rejects plans that leave zones cold at school start, and ranks survivors with a simplified energy + demand objective.

It is **not** calibrated and **must not** control a real BAS.

## How to Use It

```bash
cd vibe_code_apps_23/lessons/grid_search/scripts
python day02_fake_data_grid_search.py
```

Artifacts land under `../outputs/day02_fake_data/` (or the path you pass with `--output`):

- `grid_search_results.csv` — every candidate’s readiness and costs
- `selected_dsm_plan.json` — collapsed timed setpoint events for the winner

## Why This Matters

You need to see the **decision logic** without waiting minutes per EnergyPlus run. Once the CSV ranking makes sense, Days 03–10 only swap the toy `simulate()` for `energyplus.exe`.

## Mini Examples

```text
Menu size: 5 setbacks × 4 leads × 2 extensions = 40 candidates
Baseline: continuous 68 °F
Gate: all six zones in [68, 74] °F at 07:30 and 07:45
Rank: energy + on-peak demand + distribution demand (illustrative rates)
```

Sample decision rule from the script:

```python
selected = best_candidate if best_candidate.modeled_cost < baseline.modeled_cost else baseline
```

## Micro Exercises

1. Run the script; open the CSV; name the top admissible plan and its modeled savings vs baseline.
2. Change `COMFORT_MIN_F` from 68 to 70 and re-run — what happens to the eligible set?
3. Shrink the menu to two setbacks and one lead; confirm the loop still prints a decision.

## Key Takeaway

A tiny fake building is enough to practice **admissible search**. EnergyPlus will replace the thermal math, not the ranking philosophy.
