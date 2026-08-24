---
name: dsm-experiment-design
description: Define reproducible demand-side-management comparisons with frozen baselines, controls, comfort constraints, weather, and tariff semantics.
---

# DSM experiment design

## Goal
Compare DSM strategies against a reproducible baseline without changing weather, initial state, occupancy, tariff semantics or unrelated model parameters between arms.

## Required contract
- model hash and EnergyPlus version;
- weather hash and simulation period;
- warmup/lookback policy and initial-state provenance;
- baseline controls and candidate-only changes;
- timestep and demand interval;
- comfort limits and violation metrics;
- kWh and peak-kW metrics;
- tariff status/hash when reporting dollars.

If using a shaped RL reward, version it separately from physical/economic evaluation. A reward may include readiness, comfort, energy, demand, and action-smoothness terms, but it must not replace the published readiness constraint or tariff accounting. Preserve incumbent and candidate baseline definitions; do not relabel a modeled baseline as verified BAS behavior without source evidence.

## Recommended progression
1. Fixed schedule/setpoint grid search.
2. Weather-triggered preconditioning.
3. Supply-air/static/reset strategies when topology supports them.
4. Demand-limit or peak-aware supervisory control.
5. MPC/RL only after transparent comparators exist.

Report kWh, peak kW, time of peak, comfort/unmet hours and cost separately. A lower peak with unacceptable comfort or a large energy penalty is not automatically a better strategy.
