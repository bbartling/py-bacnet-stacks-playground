# Day 06 – Demand-Limiting Arms

*Vibe 23 Grid Search track | Lesson 6 of 10*

## Goal

Search over **facility demand caps** using the stock `5ZoneAirCooledDemandLimiting.idf` example — EnergyPlus’s built-in DemandManager stack — on a summer day.

## Concept

Instead of only heating setbacks, the candidate axis is the daytime value of `Limit Schedule` (Watts). Outside 08:00–20:00 the limit is left effectively unlimited; during peak hours we try progressively tighter caps. DemandManagers then shed equipment / lights / thermostat resets per the stock object list.

This lesson uses a **July 15** run period so cooling-dominated demand limiting is visible.

## How to Use It

```bash
cd vibe_code_apps_23/lessons/grid_search/scripts
python day06_demand_limiting.py
```

Candidates: `LIMIT_OFF_9999999`, `LIMIT_15kW`, `LIMIT_12kW`, `LIMIT_10kW`, `LIMIT_8kW`.

## Why This Matters

DSM is not only night setback. Utilities care about **peak kW**. Teaching DemandManager on a stock file shows a second actuator class without inventing custom EMS.

## Mini Examples

Stock limit shape (patched per candidate):

```text
Until: 8:00  → 9999999 W
Until: 20:00 → <candidate_cap> W
Until: 24:00 → 9999999 W
```

## Micro Exercises

1. Run Day 06; which cap yields the lowest on-peak peak kW?
2. Does the tightest cap always win the dollar objective? Why or why not?
3. Skim the IDF’s `DemandManager:*` objects — list two shed actions EnergyPlus can take.

## Key Takeaway

A grid-search **axis** can be a demand limit just as easily as a thermostat setback — same loop, different actuator.
