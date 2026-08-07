# Nearest Historical Days + EnergyPlus Delta benchmark

## Purpose

A simple, explainable **engineering benchmark** for Lakeside heating DSM screening.
It is **not** operational proof and must not be labeled as measured actual.

Honesty labels:

- `SIMPLE_HYBRID_SCREENING`
- `NEAREST_DAY_BASELINE`
- `EPLUS_COUNTERFACTUAL_DELTA`

## Method

1. Accept the same midnight state + 96-step OAT forecast + strategy as the desktop hybrid.
2. Search **complete** historical REAL_BAS days **strictly before** the evaluation / simulation day.
3. Rank neighbors with a documented distance after training-period standardization:
   - weekday/weekend match
   - outdoor-temperature trajectory
   - midnight OAT, facility kW, and six zone temperatures
4. Take the pointwise **median** of `k` neighbors (default `k=10`) as the real baseline (7 targets × 96 steps).
5. Empirical **P10 / median / P90** envelopes are neighbor ranges — **not** confidence intervals.
6. Add an EnergyPlus IdealLoads+COP **counterfactual** DSM−baseline delta matched by strategy and weather/init similarity.
7. `simple_hybrid = nearest_day_baseline + eplus_delta`

## Extrapolation gate

Leave-one-day-out nearest-neighbor distances on **development** days set the OOD threshold
(default 95th percentile). If the live query exceeds the threshold or no compatible E+ delta exists:

- mark `OUT_OF_DISTRIBUTION`
- refuse strategy recommendation
- still allow an explicitly labeled exploratory view

## Training profiles

| Mode | `max_days` | Desktop library export |
|---|---|---|
| `smoke` | 36 | **refused** (`SMOKE_ONLY`) |
| `full_evaluation` | all eligible | refused (metrics only) |
| `full_deployment` | all eligible + locked-test refit | **required** (`DEPLOYMENT_REFIT`) |

Missing profile selection **fails closed** (`VIBE22_TRAINING_PROFILE` or `--profile`).

## Limitations

- IdealLoads + fixed COP ≠ GSHP plant.
- Underpowered E+ farms watermark `UNDERPOWERED_EPLUS_DELTA_LIBRARY`.
- Strategies that raise peak or energy flag `DSM_WORSENS_PEAK` / `DSM_WORSENS_ENERGY`.
- Smoke artifacts must never be promoted as operational.

## Optimization readiness (limited scope)

No general optimizer in this pass. Shared contracts live in:

- Python: `ml/simulation_contract.py`
- Rust: `desktop/src/simulation.rs`

| Contract | Role |
|---|---|
| `SimulationRequest` | midnight kW/zones, weather@96, calendar, `ControlSchedule96`, tariff, billing peak / ratchet state |
| `ControlSchedule96` | actual setpoints, enables, occupancy at every step; `strategy_id` is provenance |
| `SimulationResult` | facility_kw[96], zones[96][6], kWh, peak, energy $, incremental demand, comfort, OOD, honesty |

**Incremental demand (one day):**

```
new_billing_peak = max(existing_billing_peak, simulated_day_peak)
incremental_demand_kw = new_billing_peak - existing_billing_peak
incremental_demand_cost = incremental_demand_kw * demand_rate
```

**STRATEGY ENUMERATION** (desktop: “Evaluate all available strategies”) ranks named strategies
by energy + incremental demand after rejecting OOD / comfort failures. Not mathematical optimization.

**24/7** remains an explicit diagnostic counterfactual button — not the automatic savings baseline.

**Annual** rollups stay labeled **HEURISTIC**. Future **Annual Replay** will accept 365 days,
simulate chronologically with monthly peak-to-date and verified tariff/ratchet terms.

**Nearest-day engine** may only optimize among strategies in its E+ delta library.
Arbitrary `ControlSchedule96` without a compatible delta returns `UNSUPPORTED_CONTROL_SCHEDULE`
(never interpolate unsupported control logic without an explicit validated method).

Future objective (documented only):

```
total_cost =
    sum(interval_kw * interval_hours * energy_rate)
  + incremental_monthly_demand_cost
  + comfort_penalty
  + equipment_cycling_penalty
```

Comfort limits should normally be hard feasibility constraints.
