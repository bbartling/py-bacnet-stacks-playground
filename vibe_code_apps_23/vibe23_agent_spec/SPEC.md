# Vibe 23 Agentic Spec — Residential Heat-Pump DSM

**Project:** Vibe Code App 23  
**Product:** Educational residential EnergyPlus DSM laboratory  
**Claim:** `HYPOTHETICAL_GL14_TUNED_DEMO_MODEL` (no measured GL14 calibration)

## Purpose
Demonstrate a heat-pump home as a thermal battery, optimize finite thermostat schedules under illustrative TOU prices, then co-optimize with a home battery — all at 5-minute zone resolution on native Windows EnergyPlus.

## Architecture
```text
residential IDF (Carrier 50EZ060)
  + Denver-type EPW (Golden/NREL TMY3)
  + illustrative TOU fixtures (288 intervals)
  -> DR demo
  -> deterministic thermostat grid search (vibe23.grid)
  -> battery dispatch on purchased-grid load
  -> compute telemetry + plots + ranking artifacts
```

## Phase gates
1. `residential-doctor` — native E+ ready
2. Smoke Jan/Jul baselines — 0 fatal
3. July DR comparison + plots
4. Summer + winter thermostat grids ranked by illustrative cost
5. Battery thermal/battery/combined comparison
6. Tests + README handoff green

## Non-goals
- Real utility bills / verified account tariffs
- Fabricated Guideline 14 metrics
- Docker/WSL as acceptance gates
- LBNL Building 59 as the active modeling target

## Preserve
`lessons/grid_search/` especially Day 10 BESS patterns.
