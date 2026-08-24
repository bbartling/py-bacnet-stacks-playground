---
name: energyplus-calibration
description: Calibrate an existing-building EnergyPlus model against measured energy and operational evidence using auditable Guideline-14-style scorecards.
---

# EnergyPlus existing-building calibration

## Goal
Build an auditable EnergyPlus model aligned to measured energy, demand and operating behavior before DSM claims are made.

## Calibration ladder
1. Freeze measured-data period, timezone, interval semantics and weather source.
2. Inventory known geometry, envelope, occupancy, HVAC topology, capacities, controls and meters; reconcile meter scope with modeled scope.
3. Record source facts vs assumptions in a parameter/evidence ledger.
4. Build the simplest model that preserves the real behavior required by the study.
5. Match schedules and base loads before tuning efficiencies.
6. Match seasonal/end-use behavior before chasing annual totals.
7. Compare monthly and, where available, hourly/sub-hourly load shape and peak demand.
8. Change a small documented parameter group per iteration; persist hashes and scorecards.
9. Hold out a period when enough data exist.

When inheriting a campaign that failed its variability or physics gates, freeze
its model, weather, target, and result hashes as historical evidence. Audit
meter scope, operational telemetry, and structural mismatches before launching
more parameter search. A low annual bias caused by compensating end-use errors
is not a useful calibration starting point.

For a sparse-data seed, use a transparent defaults hierarchy and label every default. Do not use a passing monthly score to erase unsupported geometry, controls, fuel, or meter-allocation assumptions. A conventional tuning order is: meter scope/schedules and internal loads, geometry/envelope/infiltration, ventilation/fan/runtime, then plant/equipment performance and control behavior. If a change improves one fuel while materially degrading another, record the tradeoff rather than silently selecting by annual total.

## Default ASHRAE Guideline 14-style gates
- Monthly: `|NMBE| <= 5%`, `CV(RMSE) <= 15%`.
- Hourly: `|NMBE| <= 10%`, `CV(RMSE) <= 30%`.

Passing aggregate statistics does not prove every physical input is correct. Also inspect peak kW, time of peak, end uses, equipment runtime and zone temperatures.

Admit a run for scoring only after checking the EnergyPlus exit code, zero
warning/severe/fatal diagnostics (when that is the project's declared gate),
complete ancillary outputs, and the expected number of reporting intervals.
Do not call a repeatedly inspected period a blind holdout; label it a reserved
diagnostic slice and establish a new untouched period for validation.

## Status ladder
`MODEL_SEED` · `CALIBRATION_IN_PROGRESS` · `MONTHLY_CALIBRATED` · `HOURLY_CALIBRATED` · `VALIDATED_HOLDOUT`
