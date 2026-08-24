---
name: energyplus-demand-management
description: Design EnergyPlus demand-response or load-shift scenarios with explicit controls, comfort gates, actual interval demand, and simulation-only claim boundaries.
---

# EnergyPlus demand management

Use for setpoint relaxation, deadband widening, preconditioning, availability changes, capacity limits, or other supervisory demand-control experiments.

Specify the action window, baseline, weather, occupancy, equipment/control impact, facility-demand meter, comfort constraints, and rebound window. Evaluate peak magnitude/time, kWh, demand interval, comfort/unmet hours, and post-event rebound. Keep synthetic training data and modeled trajectories labeled as simulation outputs; no scenario grants live BACnet authority.

Use `dsm-experiment-design` for comparison contract, `utility-tariff` for tariff status, and `grid-search-dsm` or `policy-evaluation` for decision experiments.
