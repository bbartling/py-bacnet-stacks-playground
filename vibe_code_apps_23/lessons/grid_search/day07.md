# Day 07 – Night Ventilation Comparison

*Vibe 23 Grid Search track | Lesson 7 of 10*

## Goal

Compare the stock night-ventilation pair — `5ZoneNightVent1.idf` (documented **no** night vent) vs `5ZoneNightVent2.idf` (Ventilation-object night venting) — while also sweeping a small heating-setpoint grid on a summer day.

## Concept

Sometimes the “candidate” is not only a schedule number but a **model variant**. Day 07 treats `{NO_NV, WITH_NV} × setback × lead` as the menu. That mirrors how a research pack might import two reference arms and only then search continuous knobs.

## How to Use It

```bash
cd vibe_code_apps_23/lessons/grid_search/scripts
python day07_night_ventilation.py
```

Run day: July 20 (Chicago TMY3). Ranking uses the same illustrative electricity + demand objective (readiness heating gate disabled for this summer lesson).

## Why This Matters

Night flush / night vent is a classic passive DSM lever. Seeing NightVent1 vs NightVent2 side-by-side trains you to keep **model identity** in the results CSV (`extra.model` / `night_vent` tags).

## Mini Examples

| Tag | ExampleFile | Intent |
| --- | --- | --- |
| NO_NV | `5ZoneNightVent1.idf` | Base case without night ventilation |
| WITH_NV | `5ZoneNightVent2.idf` | Night ventilation via `ZoneVentilation:DesignFlowRate` |

## Micro Exercises

1. After the run, sort CSV by `objective_usd` — does WITH_NV dominate?
2. Open both IDF headers’ “Highlights” comments; quote one sentence each.
3. Propose a third axis (e.g. night-vent flow multiplier) and estimate new menu size.

## Key Takeaway

Grid search can span **discrete model arms** and **continuous-ish schedule knobs** in one ranked table — as long as every row is labeled.
