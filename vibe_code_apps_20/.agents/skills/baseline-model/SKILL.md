# Skill: baseline-model

Create and freeze a defensible EnergyPlus baseline for OpenFDD WattLab.

## Steps

1. Select prototype IDF (`5ZoneAirCooled` default).
2. Attach EPW via `epw-climate`.
3. Apply baseline schedule/HVAC archetype patch if screening inefficient runtime.
4. Simulate; store `result_record` + IDF SHA-256.
5. Freeze: no silent default acceptance without flags.

## Related

`building-intake`, `hvac-mapping`, `easy-button-calibrate`
