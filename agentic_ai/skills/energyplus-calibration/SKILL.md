# Skill — EnergyPlus Existing-Building Calibration

## Goal
Build an auditable EnergyPlus model aligned to measured energy, demand and operating behavior before DSM claims are made.

## Calibration ladder
1. Freeze measured-data period, timezone, interval semantics and weather source.
2. Inventory known geometry, envelope, occupancy, HVAC topology, capacities, controls and meters.
3. Record source facts vs assumptions in a parameter/evidence ledger.
4. Build the simplest model that preserves the real behavior required by the study.
5. Match schedules and base loads before tuning efficiencies.
6. Match seasonal/end-use behavior before chasing annual totals.
7. Compare monthly and, where available, hourly/sub-hourly load shape and peak demand.
8. Change a small documented parameter group per iteration; persist hashes and scorecards.
9. Hold out a period when enough data exist.

## Default ASHRAE Guideline 14-style gates
- Monthly: `|NMBE| <= 5%`, `CV(RMSE) <= 15%`.
- Hourly: `|NMBE| <= 10%`, `CV(RMSE) <= 30%`.

Passing aggregate statistics does not prove every physical input is correct. Also inspect peak kW, time of peak, end uses, equipment runtime and zone temperatures.

## Status ladder
`MODEL_SEED` · `CALIBRATION_IN_PROGRESS` · `MONTHLY_CALIBRATED` · `HOURLY_CALIBRATED` · `VALIDATED_HOLDOUT`
