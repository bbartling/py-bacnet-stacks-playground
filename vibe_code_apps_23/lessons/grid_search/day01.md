# Day 01 – Grid-Search Pseudocode (DSM Mental Model)

*Vibe 23 Grid Search track | Lesson 1 of 10*

## Goal

Explain the **bounded grid-search** pattern for daily HVAC demand-side management (DSM) in plain language and pseudocode — before any simulator runs. By the end you can sketch the loop on a whiteboard.

## Concept

Grid search here does **not** mean “optimize every continuous parameter.” It means:

1. Build a **small, human-readable menu** of daily plans (setback × recovery lead × maybe extension).
2. **Simulate** each plan for one forecast day.
3. **Reject** plans that fail a readiness / comfort gate.
4. **Rank** the survivors with a transparent energy + demand objective.
5. Keep the **baseline** unless a candidate clearly wins.

EnergyPlus (later lessons) is only the scoring engine. The search itself is deliberately boring and finite.

## How to Use It

Read this pseudocode aloud; map each line to a real building decision:

```text
INPUT: tomorrow's outdoor forecast, baseline HVAC schedule, tariff sketch

menu ← product(setbacks, recovery_leads, extensions)   # e.g. 5 × 4 × 2 = 40

FOR each candidate IN menu:
    schedule ← expand_candidate_to_15min_setpoints(candidate)
    timeseries ← simulate_building(schedule, forecast)   # toy OR EnergyPlus
    ready ← school_zones_in_comfort_at_bell(timeseries)
    IF NOT ready:
        mark INADMISSIBLE
        CONTINUE
    score ← energy_cost(timeseries) + demand_cost(timeseries)
    record (candidate, score, peak_kW, kWh)

eligible ← all recorded with ready == true
IF eligible is empty:
    DECISION ← keep baseline; publish NO override
ELSE:
    best ← argmin(score over eligible)
    IF best.score < baseline.score:
        DECISION ← publish timed setpoint events from best
    ELSE:
        DECISION ← keep baseline
```

## Why This Matters

Operators will not trust a black-box RL agent that mutates hundreds of knobs. A finite menu of setback/recovery plans is **auditable**: you can say “we tested these 16 schedules; three failed readiness; this one saved modeled dollars.”

## Mini Examples

| Piece | Toy lesson (Day 02) | EnergyPlus lessons (Days 04+) |
| --- | --- | --- |
| Forecast | Hard-coded cold January hours | Chicago TMY3 EPW day |
| Simulate | 6-zone RC-ish loop | `energyplus.exe -w …` |
| Readiness | Zones ≥ 68 °F at 07:30–07:45 | Zone Mean Air Temperature at bell |
| Rank | Illustrative $/kWh + $/kW | Same illustrative objective |

## Micro Exercises

1. Write the pseudocode from memory on paper (no peeking).
2. List three reasons a candidate might be **inadmissible** even if it looks cheap.
3. Explain why “keep baseline unless a candidate wins” is safer than “always publish the argmin.”

## Key Takeaway

**Grid search chooses which understandable daily schedules to test; the building model (toy or EnergyPlus) scores them.** Readiness is a hard gate; cost is only a ranking among survivors.
