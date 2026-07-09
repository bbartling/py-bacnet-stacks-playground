# Rust + DataFusion parity benchmark

Generated: 2026-07-09 14:03 UTC

- building: `BUILDING_100`
- tolerance: `0.5`
- rules compared: 19
- equipment compared: 48
- pass: 228
- fail: 52
- skipped (missing roles): 11
- python-only keys: 250
- sql-only keys: 616
- max abs delta: 28650.0000
- max pct delta: 88700.00%
- material failure: true

## Summary by rule

| rule | pass | fail | skipped | max Δ | max % | worst equipment |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| FAULT-ELAPSED-HOURS | 60 | 2 | 1 | 28650.000 | 90.7% | VAV_7 |
| VAV-1 | 36 | 26 | 1 | 2389.367 | 90.8% | VAV_7 |
| AVG-ZONE-TEMP | 90 | 3 | 1 | 887.000 | 88700.0% | VAV_7 |
| ZONE-COMFORT-PCT | 30 | 1 | 1 | 90.731 | 100.0% | VAV_7 |
| OAT-METEO | 0 | 4 | 0 | 32.733 | 7.9% | AHU_2 |
| FC8 | 0 | 2 | 0 | 29.767 | 2.0% | AHU_1 |
| ECON-4 | 0 | 2 | 0 | 26.033 | 5.6% | AHU_1 |
| FC13-SAT-HIGH | 0 | 2 | 0 | 21.017 | 6.0% | AHU_2 |
| FC10 | 0 | 2 | 0 | 20.283 | 3.9% | AHU_2 |
| FC2 | 0 | 2 | 0 | 17.667 | 24.6% | AHU_2 |
| FC9 | 0 | 2 | 0 | 17.550 | 1.2% | AHU_2 |
| ECON-2 | 0 | 2 | 0 | 8.283 | 0.7% | AHU_2 |
| FC12 | 0 | 2 | 0 | 1.617 | 90.5% | AHU_1 |
| FC7 | 0 | 0 | 2 | 0.000 | - | - |
| FAN-RUNTIME-HOURS | 4 | 0 | 3 | 0.000 | - | - |
| ECON-1 | 2 | 0 | 0 | 0.000 | - | - |
| FC11 | 2 | 0 | 0 | 0.000 | - | - |
| FC1 | 2 | 0 | 0 | 0.000 | - | - |
| FC3 | 2 | 0 | 0 | 0.000 | - | - |
| ECON-5 | 0 | 0 | 2 | 0.000 | - | - |

## Summary by equipment (failures only)

| equipment | failed rules | fail metrics | max Δ |
| --- | --- | ---: | ---: |
| VAV_7 | AVG-ZONE-TEMP, FAULT-ELAPSED-HOURS, VAV-1, ZONE-COMFORT-PCT | 8 | 28650.000 |
| AHU_2 | ECON-2, ECON-4, FC10, FC12, FC13-SAT-HIGH, FC2, FC8, FC9, OAT-METEO | 10 | 32.733 |
| AHU_1 | ECON-2, ECON-4, FC10, FC12, FC13-SAT-HIGH, FC2, FC8, FC9, OAT-METEO | 10 | 29.767 |
| VAV_10 | VAV-1 | 1 | 7.317 |
| VAVFC_100 | VAV-1 | 1 | 6.800 |
| VAVH_115 | VAV-1 | 1 | 4.333 |
| VAV_8 | VAV-1 | 1 | 4.083 |
| VAV_3 | VAV-1 | 1 | 3.850 |
| VAV_21 | VAV-1 | 1 | 2.067 |
| VAV_23 | VAV-1 | 1 | 2.033 |
| VAV_24 | VAV-1 | 1 | 2.033 |
| VAV_9 | VAV-1 | 1 | 1.767 |
| VAV_20 | VAV-1 | 1 | 1.717 |
| VAV_22 | VAV-1 | 1 | 1.567 |
| VAV_113 | VAV-1 | 1 | 1.417 |
| VAV_11 | VAV-1 | 1 | 1.400 |
| VAV_2 | VAV-1 | 1 | 1.250 |
| VAV_114 | VAV-1 | 1 | 1.183 |
| VAV_18 | VAV-1 | 1 | 1.033 |
| VAV_19 | VAV-1 | 1 | 1.033 |
| VAV_108 | VAV-1 | 1 | 0.967 |
| VAV_106 | VAV-1 | 1 | 0.967 |
| VAV_12 | VAV-1 | 1 | 0.733 |
| VAVH_109 | VAV-1 | 1 | 0.717 |
| VAV_13 | VAV-1 | 1 | 0.633 |
| VAV_1 | VAV-1 | 1 | 0.550 |
| VAV_16 | VAV-1 | 1 | 0.550 |

## Top 20 mismatches (absolute delta)

| rule | equipment | metric | python | sql | delta | pct |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| FAULT-ELAPSED-HOURS | VAV_7 | fault_samples | 31577.000 | 2927.000 | 28650.000 | 90.7% |
| VAV-1 | VAV_7 | fault_hours | 2631.200 | 241.833 | 2389.367 | 90.8% |
| FAULT-ELAPSED-HOURS | VAV_7 | fault_hours | 2631.417 | 243.917 | 2387.500 | 90.7% |
| AVG-ZONE-TEMP | VAV_7 | max_zone_temp | 1.000 | 888.000 | 887.000 | 88700.0% |
| VAV-1 | VAV_7 | fault_pct | 99.990 | 9.190 | 90.800 | 90.8% |
| ZONE-COMFORT-PCT | VAV_7 | comfort_pct | 0.000 | 90.731 | 90.731 | 100.0% |
| AVG-ZONE-TEMP | VAV_7 | avg_zone_temp | 1.000 | 72.949 | 71.949 | 7194.9% |
| AVG-ZONE-TEMP | VAV_7 | min_zone_temp | 1.000 | 64.779 | 63.779 | 6377.9% |
| OAT-METEO | AHU_2 | fault_hours | 1086.600 | 1119.333 | 32.733 | 3.0% |
| FC8 | AHU_1 | fault_hours | 1461.900 | 1491.667 | 29.767 | 2.0% |
| ECON-4 | AHU_1 | fault_hours | 464.800 | 490.833 | 26.033 | 5.6% |
| FC8 | AHU_2 | fault_hours | 1541.000 | 1567.000 | 26.000 | 1.7% |
| OAT-METEO | AHU_1 | fault_hours | 285.400 | 307.833 | 22.433 | 7.9% |
| FC13-SAT-HIGH | AHU_2 | fault_hours | 350.900 | 371.917 | 21.017 | 6.0% |
| FC10 | AHU_2 | fault_hours | 516.300 | 536.583 | 20.283 | 3.9% |
| FC2 | AHU_2 | fault_hours | 317.500 | 335.167 | 17.667 | 5.6% |
| FC9 | AHU_2 | fault_hours | 1506.700 | 1524.250 | 17.550 | 1.2% |
| FC10 | AHU_1 | fault_hours | 788.500 | 804.750 | 16.250 | 2.1% |
| FC13-SAT-HIGH | AHU_1 | fault_hours | 292.600 | 303.917 | 11.317 | 3.9% |
| ECON-2 | AHU_2 | fault_hours | 1433.700 | 1425.417 | 8.283 | 0.6% |

## Top 20 mismatches (percent delta)

| rule | equipment | metric | python | sql | delta | pct |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| AVG-ZONE-TEMP | VAV_7 | max_zone_temp | 1.000 | 888.000 | 887.000 | 88700.0% |
| AVG-ZONE-TEMP | VAV_7 | avg_zone_temp | 1.000 | 72.949 | 71.949 | 7194.9% |
| AVG-ZONE-TEMP | VAV_7 | min_zone_temp | 1.000 | 64.779 | 63.779 | 6377.9% |
| ZONE-COMFORT-PCT | VAV_7 | comfort_pct | 0.000 | 90.731 | 90.731 | 100.0% |
| VAV-1 | VAV_7 | fault_hours | 2631.200 | 241.833 | 2389.367 | 90.8% |
| VAV-1 | VAV_7 | fault_pct | 99.990 | 9.190 | 90.800 | 90.8% |
| FAULT-ELAPSED-HOURS | VAV_7 | fault_hours | 2631.417 | 243.917 | 2387.500 | 90.7% |
| FAULT-ELAPSED-HOURS | VAV_7 | fault_samples | 31577.000 | 2927.000 | 28650.000 | 90.7% |
| FC12 | AHU_2 | fault_hours | 1.400 | 2.667 | 1.267 | 90.5% |
| FC2 | AHU_1 | fault_hours | 20.000 | 24.917 | 4.917 | 24.6% |
| FC12 | AHU_1 | fault_hours | 15.800 | 17.417 | 1.617 | 10.2% |
| OAT-METEO | AHU_1 | fault_hours | 285.400 | 307.833 | 22.433 | 7.9% |
| OAT-METEO | AHU_1 | fault_pct | 10.850 | 11.698 | 0.848 | 7.8% |
| FC13-SAT-HIGH | AHU_2 | fault_hours | 350.900 | 371.917 | 21.017 | 6.0% |
| ECON-4 | AHU_1 | fault_hours | 464.800 | 490.833 | 26.033 | 5.6% |
| FC2 | AHU_2 | fault_hours | 317.500 | 335.167 | 17.667 | 5.6% |
| FC10 | AHU_2 | fault_hours | 516.300 | 536.583 | 20.283 | 3.9% |
| FC13-SAT-HIGH | AHU_1 | fault_hours | 292.600 | 303.917 | 11.317 | 3.9% |
| VAV-1 | VAV_3 | fault_hours | 110.900 | 114.750 | 3.850 | 3.5% |
| VAV-1 | VAV_1 | fault_hours | 16.200 | 16.750 | 0.550 | 3.4% |

## Proven parity

- `FAN-RUNTIME-HOURS`
- `ECON-1`
- `FC11`
- `FC1`
- `FC3`

## Near parity

_None._

## Material mismatch

- `FAULT-ELAPSED-HOURS`
- `VAV-1`
- `AVG-ZONE-TEMP`
- `ZONE-COMFORT-PCT`
- `OAT-METEO`
- `FC8`
- `ECON-4`
- `FC13-SAT-HIGH`
- `FC10`
- `FC2`
- `FC9`
- `ECON-2`
- `FC12`

## Skipped due to missing roles

- `FC7` / `AHU_1`: missing roles: htg_valve_pct
- `ECON-5` / `AHU_1`: missing roles: preheat_leave_t, htg_valve_pct
- `FC7` / `AHU_2`: missing roles: htg_valve_pct
- `ECON-5` / `AHU_2`: missing roles: preheat_leave_t, htg_valve_pct
- `FAN-RUNTIME-HOURS` / `BOILERS_PUMPS`: missing roles: fan_cmd
- `FAN-RUNTIME-HOURS` / `CHILLER_1`: missing roles: fan_cmd
- `FAN-RUNTIME-HOURS` / `CHILLER_2`: missing roles: fan_cmd
- `VAV-1` / `VAV_25A`: missing roles: zone_t
- `AVG-ZONE-TEMP` / `VAV_25A`: missing roles: zone_t
- `ZONE-COMFORT-PCT` / `VAV_25A`: missing roles: zone_t
- `FAULT-ELAPSED-HOURS` / `VAV_25A`: missing roles: zone_t

## Proxy / partial implementation

- Review registry `parity_status` and blockers for rules not yet oracle-aligned.
- `OAT-METEO` (weather/threshold proxy path)

## All mismatches

| rule | equipment | metric | python | sql | delta | pct |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| FC12 | AHU_2 | fault_hours | 1.400 | 2.667 | 1.267 | 90.5% |
| ECON-4 | AHU_1 | fault_hours | 464.800 | 490.833 | 26.033 | 5.6% |
| VAV-1 | VAV_8 | fault_hours | 366.000 | 370.083 | 4.083 | 1.1% |
| ECON-2 | AHU_1 | fault_hours | 1093.000 | 1085.583 | 7.417 | 0.7% |
| VAV-1 | VAVH_109 | fault_hours | 1007.200 | 1007.917 | 0.717 | 0.1% |
| VAV-1 | VAV_11 | fault_hours | 211.600 | 213.000 | 1.400 | 0.7% |
| VAV-1 | VAV_13 | fault_hours | 58.700 | 59.333 | 0.633 | 1.1% |
| AVG-ZONE-TEMP | VAV_7 | avg_zone_temp | 1.000 | 72.949 | 71.949 | 7194.9% |
| FC2 | AHU_2 | fault_hours | 317.500 | 335.167 | 17.667 | 5.6% |
| VAV-1 | VAVFC_100 | fault_hours | 1524.200 | 1531.000 | 6.800 | 0.4% |
| OAT-METEO | AHU_2 | fault_pct | 41.290 | 42.537 | 1.247 | 3.0% |
| VAV-1 | VAV_20 | fault_hours | 163.200 | 164.917 | 1.717 | 1.1% |
| VAV-1 | VAV_113 | fault_hours | 74.500 | 75.917 | 1.417 | 1.9% |
| VAV-1 | VAV_9 | fault_hours | 204.900 | 206.667 | 1.767 | 0.9% |
| FC12 | AHU_1 | fault_hours | 15.800 | 17.417 | 1.617 | 10.2% |
| FC8 | AHU_1 | fault_hours | 1461.900 | 1491.667 | 29.767 | 2.0% |
| FAULT-ELAPSED-HOURS | VAV_7 | fault_samples | 31577.000 | 2927.000 | 28650.000 | 90.7% |
| VAV-1 | VAV_10 | fault_hours | 1272.600 | 1279.917 | 7.317 | 0.6% |
| VAV-1 | VAV_3 | fault_hours | 110.900 | 114.750 | 3.850 | 3.5% |
| FC2 | AHU_1 | fault_hours | 20.000 | 24.917 | 4.917 | 24.6% |
| ZONE-COMFORT-PCT | VAV_7 | comfort_pct | 0.000 | 90.731 | 90.731 | 100.0% |
| VAV-1 | VAV_21 | fault_hours | 228.600 | 230.667 | 2.067 | 0.9% |
| VAV-1 | VAV_7 | fault_pct | 99.990 | 9.190 | 90.800 | 90.8% |
| VAV-1 | VAV_16 | fault_hours | 22.200 | 22.750 | 0.550 | 2.5% |
| FC8 | AHU_2 | fault_hours | 1541.000 | 1567.000 | 26.000 | 1.7% |
| VAV-1 | VAV_19 | fault_hours | 123.800 | 124.833 | 1.033 | 0.8% |
| VAV-1 | VAV_7 | fault_hours | 2631.200 | 241.833 | 2389.367 | 90.8% |
| FC10 | AHU_1 | fault_hours | 788.500 | 804.750 | 16.250 | 2.1% |
| ECON-4 | AHU_2 | fault_hours | 360.600 | 365.917 | 5.317 | 1.5% |
| AVG-ZONE-TEMP | VAV_7 | max_zone_temp | 1.000 | 888.000 | 887.000 | 88700.0% |
| OAT-METEO | AHU_1 | fault_hours | 285.400 | 307.833 | 22.433 | 7.9% |
| FC9 | AHU_1 | fault_hours | 628.600 | 635.083 | 6.483 | 1.0% |
| VAV-1 | VAV_108 | fault_hours | 37.700 | 38.667 | 0.967 | 2.6% |
| VAV-1 | VAV_2 | fault_hours | 75.000 | 76.250 | 1.250 | 1.7% |
| VAV-1 | VAV_24 | fault_hours | 239.800 | 241.833 | 2.033 | 0.8% |
| ECON-2 | AHU_2 | fault_hours | 1433.700 | 1425.417 | 8.283 | 0.6% |
| VAV-1 | VAV_114 | fault_hours | 55.400 | 56.583 | 1.183 | 2.1% |
| FC13-SAT-HIGH | AHU_1 | fault_hours | 292.600 | 303.917 | 11.317 | 3.9% |
| OAT-METEO | AHU_2 | fault_hours | 1086.600 | 1119.333 | 32.733 | 3.0% |
| VAV-1 | VAV_18 | fault_hours | 123.800 | 124.833 | 1.033 | 0.8% |
| FAULT-ELAPSED-HOURS | VAV_7 | fault_hours | 2631.417 | 243.917 | 2387.500 | 90.7% |
| VAV-1 | VAV_12 | fault_hours | 82.100 | 82.833 | 0.733 | 0.9% |
| FC13-SAT-HIGH | AHU_2 | fault_hours | 350.900 | 371.917 | 21.017 | 6.0% |
| VAV-1 | VAV_22 | fault_hours | 636.100 | 637.667 | 1.567 | 0.2% |
| VAV-1 | VAVH_115 | fault_hours | 185.500 | 189.833 | 4.333 | 2.3% |
| OAT-METEO | AHU_1 | fault_pct | 10.850 | 11.698 | 0.848 | 7.8% |
| FC9 | AHU_2 | fault_hours | 1506.700 | 1524.250 | 17.550 | 1.2% |
| VAV-1 | VAV_23 | fault_hours | 239.800 | 241.833 | 2.033 | 0.8% |
| AVG-ZONE-TEMP | VAV_7 | min_zone_temp | 1.000 | 64.779 | 63.779 | 6377.9% |
| FC10 | AHU_2 | fault_hours | 516.300 | 536.583 | 20.283 | 3.9% |
| VAV-1 | VAV_106 | fault_hours | 37.700 | 38.667 | 0.967 | 2.6% |
| VAV-1 | VAV_1 | fault_hours | 16.200 | 16.750 | 0.550 | 3.4% |
