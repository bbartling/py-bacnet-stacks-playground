---
name: grid-search-dsm
description: Run transparent, bounded EnergyPlus grid searches for daily DSM planning, with identical-state comparators, readiness gates, compute budgets, and tariff-separated rankings.
---

# Grid-search DSM

Use this before RL for a daily planning study or whenever an auditable comparator is needed.

1. Freeze model, weather, initial-state/lookback, occupancy, baseline, action lattice, comfort/readiness gate, demand window, and tariff contract.
2. Run a smoke/micro gate, then pilot timing/determinism checks before exhaustive search. If exhaustive evaluation exceeds the preregistered time budget, use a declared bounded subset; do not call it exhaustive.
3. For adaptive daily selection, compare candidates from the same midnight state and use only information available then. Keep this distinct from a fixed-policy multi-day replay.
4. Select the lowest-cost fully-ready candidate; record kWh, peak kW/time, comfort, compute resources, trajectory/model hashes, and candidate coverage.
5. Keep rankings separate across tariff contracts. Grid search selects explicit cost subject to gates; it is not an RL reward result.

No BACnet command authority follows from a simulation screen.
