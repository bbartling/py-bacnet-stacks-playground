# Day 05 – Expand the Menu (WLHP Full Grid)

*Vibe 23 Grid Search track | Lesson 5 of 10*

## Goal

Scale Day 04’s thermostat search to a **4×4 menu** (16 EnergyPlus runs) on the same water-loop heat pump example — matching the shape of `energyplus_grid_search_demo.py`.

## Concept

Same model, same readiness gate, same illustrative objective — only the candidate product grows:

```text
setbacks ∈ {60, 62, 64, 68} °F
leads    ∈ {0, 1, 2, 3} h
→ 16 understandable daily schedules
```

Use `--quick` to run the four corner cases when you want a smoke test.

## How to Use It

```bash
cd vibe_code_apps_23/lessons/grid_search/scripts
python day05_expand_menu.py --quick          # 4 runs
python day05_expand_menu.py                  # full 16 runs
```

Read `../outputs/day05_expand_menu/grid_search_results.csv` and `selected_plan.json`.

## Why This Matters

Grid search cost is roughly **linear in menu size**. Operators need to feel that latency before they invent a 200-cell menu. Bounded menus stay reviewable.

## Mini Examples

Console line per candidate:

```text
[07/16] SB62_LEAD2    ready=True  kWh=....  obj=$....  (12.3s)
```

Decision payload records the winner name or notes that every candidate failed readiness / quality checks.

## Micro Exercises

1. Run `--quick`; confirm four CSV rows appear.
2. Full run (optional): plot or sort by `objective_usd` among `ready==True`.
3. Add one extension-hour dimension on paper — how many runs would 4×4×2 create?

## Key Takeaway

Expanding the menu is a **product of axes**, not a smarter optimizer. Keep axes few and physically meaningful.
