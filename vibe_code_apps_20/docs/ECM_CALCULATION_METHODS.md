# ECM calculation methods

Open, independently implemented HVAC bin-method screening calculators with synthetic golden tests.

## Library

`wattlab.bench.esco` registers:

- scheduling (fan / cooling / heating)
- unoccupied OA closure
- DCV
- static-pressure reset
- DAT / SAT reset
- hydronic reset (HW / CHW / condenser wrappers)
- dew-point / enthalpy economizer screening
- pneumatic compressor avoided runtime

Weather basis: `wattlab.weather.bins.WeatherBins` (5°F × 3 shifts + MCWB).

## Conventions

- Sensible: `1.08 * CFM * dT` (IP screening)
- Total enthalpy vent: `4.5 * CFM * dh`
- Cooling electricity: ton-hours × kW/ton
- Heating fuel: kBtu / boiler efficiency → therms / MMBtu
- Fan affinity: speed ∝ √(pressure ratio); power ∝ speed³

Magic numbers and defaults belong in versioned configuration with unit, source, applicability, and confidence. See calculator provenance records for applicability limits.

## Goldens

`tests/test_esco_golden.py` uses synthetic deterministic fixtures and transparent expected values. Private workbook cell addresses and client schedules are not required.
