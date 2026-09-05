# Day 08 – Small Office Reference Building

*Vibe 23 Grid Search track | Lesson 8 of 10*

## Goal

Move from five-zone teaching IDFs to a **DOE Commercial Reference Building**: `RefBldgSmallOfficeNew2004_Chicago.idf`. Run a modest heating setback × recovery grid for one Chicago winter day.

## Concept

Reference buildings are still ExampleFiles, but they behave more like “real-ish” offices: multiple zones, packaged HVAC, richer schedules (`HTGSETP_SCH`, occupancy, lights). The search loop is unchanged — only the IDF and schedule name change.

## How to Use It

```bash
cd lessons/grid_search/scripts
python day08_small_office.py
```

Menu: setbacks `{60, 64, 68}` °F × leads `{0, 2}` h → 6 runs.

## Why This Matters

If your mental model only works on `5ZoneWaterLoopHeatPump`, it will not transfer. Day 08 proves the helpers (`replace_object`, readiness parse, ranking) survive a larger stock model.

## Mini Examples

Schedule object replaced: `HTGSETP_SCH` (Temperature).

Readiness still checks Zone Mean Air Temperature near 08:00 / 08:15 against ≥ 68 °F (occupied zones, excluding plenums when labeled).

## Micro Exercises

1. Run Day 08; note how runtime compares to Day 04.
2. Which candidate fails readiness first as setback deepens?
3. Find `BLDG_OCC_SCH` in the IDF — when does occupancy ramp up relative to your recovery lead?

## Key Takeaway

**Reference buildings** are the bridge between toy five-zone files and later calibrated sites — same DSM loop, heavier geometry.
