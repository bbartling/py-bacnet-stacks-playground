# Schedules

## Purpose
Map observed or documented operation into EnergyPlus schedule inputs.

## Invoke when
Occupancy, runtime, setback, optimum start/stop, or scheduling ECMs.

## Required inputs
- Occupancy calendar
- BAS fan status/runtime
- thermostat schedules
- holidays
- operating exceptions

## Procedure
1. Separate occupied, setup, and after-hours operation.
2. Compare BAS runtime to documented schedule.
3. Select standard defaults unless evidence supports simplified schedules.
4. Create baseline and proposed schedule matrices.
5. Identify interactions with ventilation and temperature setbacks.

## Outputs
- schedule matrix
- schedule ECM brief
- runtime evidence links

## Guardrails
Never treat a single week as annual operation without qualification. Preserve critical-process operation.

## Validation
Weekly hours reconcile; holidays documented; runtime savings do not exceed removable runtime.
