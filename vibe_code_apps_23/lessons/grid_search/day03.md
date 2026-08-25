# Day 03 – First Real EnergyPlus Run

*Vibe 23 Grid Search track | Lesson 3 of 10*

## Goal

Prove your EnergyPlus 26.1 toolchain works: locate `energyplus.exe`, run a **stock** ExampleFile for one Chicago winter day, and read `eplusout.csv`. No grid search yet.

## Concept

Before mutating schedules, confirm:

- ExampleFiles path resolves
- Weather file (Chicago O’Hare TMY3) resolves
- A one-day `RunPeriod` completes without fatals
- Timestep CSV outputs are parseable

Model: `1ZoneUncontrolled.idf` — the simplest stock zone. We inject timestep outdoor and zone-temperature outputs and force a single January 14 run.

## How to Use It

```bash
cd vibe_code_apps_23/lessons/grid_search/scripts
python day03_first_eplus_run.py
```

Optional: `set ENERGYPLUS_ROOT=C:\EnergyPlusV26-1-0`

Inspect `../outputs/day03_first_eplus/summary.json` and the run folder’s `eplusout.csv` / `eplusout.err`.

## Why This Matters

Most “grid search is broken” failures are really **path, weather, RunPeriod, or CSV column** failures. Day 03 isolates the toolchain.

## Mini Examples

```bash
# What the helper effectively runs:
energyplus.exe -w USA_IL_Chicago-OHare....epw -d <run_dir> -r candidate.idf
```

Look for columns like `Environment:Site Outdoor Air Drybulb Temperature` and `ZONE ONE:Zone Mean Air Temperature`.

## Micro Exercises

1. Run Day 03; write down runtime seconds and CSV row count.
2. Open `eplusout.err` — count `** Severe **` / `** Fatal **` (should be zero fatals).
3. Change the script’s run day from Jan 14 to Jan 21 and re-run; confirm OAT stats move.

## Key Takeaway

**One clean EnergyPlus run** is the unit of work for every later grid-search cell. Get this boring step right first.
