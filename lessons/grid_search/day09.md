# Day 09 – Primary School Occupancy-Aware Readiness

*Vibe 23 Grid Search track | Lesson 9 of 10*

## Goal

Apply grid search to `RefBldgPrimarySchoolNew2004_Chicago.idf` with a **school-shaped readiness gate** (temperatures checked at 07:30, 07:45, and 08:00) and occupied heating ending mid-afternoon.

## Concept

Schools punish late recovery: a cheap deep setback that is still cold at first bell is **inadmissible**, regardless of modeled dollars. Day 09 makes that gate explicit and uses a denser lead-time axis (`1, 2, 3` h) because recovery timing is the story.

Use `--quick` for three representative candidates when iterating.

## How to Use It

```bash
cd lessons/grid_search/scripts
python day09_primary_school.py --quick
python day09_primary_school.py              # full 9-run menu (slower)
```

## Why This Matters

This is the closest ExampleFile lesson to the Vibe22 “school readiness” narrative — still stock, still educational, but the **fail-closed** mindset matches operator reality.

## Mini Examples

```text
ready_clocks = (07:30, 07:45, 08:00)
occupied heating window ends ~16:00
menu = {60,62,66} °F × {1,2,3} h lead
```

## Micro Exercises

1. With `--quick`, record which plans are ready vs not.
2. Argue why lead=1 with SB60 is riskier than lead=3 with SB66.
3. List two zones/schedule names unique to the primary-school IDF (cafeteria, gym, …).

## Key Takeaway

**Readiness before dollars.** Grid search without an occupancy-aware gate will happily “win” on cost while failing the building’s actual job.
