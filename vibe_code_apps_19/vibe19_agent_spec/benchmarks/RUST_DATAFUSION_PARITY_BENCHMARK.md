# Rust + DataFusion parity benchmark

Generated: 2026-07-09 16:36 UTC

- building: `BUILDING_100`
- tolerance: `0.5`
- rules compared: 19
- equipment compared: 48
- pass: 320
- fail: 48
- skipped (missing roles): 11
- python-only keys: 162
- sql-only keys: 616
- max abs delta: 29.7667
- max pct delta: 100.00%
- material failure: true

## Summary by rule

| rule | pass | fail | skipped | max Δ | max % | worst equipment |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| FC8 | 0 | 2 | 0 | 29.767 | 2.0% | AHU_1 |
| FC13-SAT-HIGH | 0 | 2 | 0 | 21.017 | 6.0% | AHU_2 |
| FC10 | 0 | 2 | 0 | 20.283 | 3.9% | AHU_2 |
| FC2 | 0 | 2 | 0 | 17.667 | 24.6% | AHU_2 |
| FC9 | 0 | 2 | 0 | 17.550 | 1.2% | AHU_2 |
| ECON-2 | 0 | 2 | 0 | 8.283 | 0.7% | AHU_2 |
| VAV-1 | 50 | 34 | 1 | 6.800 | 4.7% | VAVFC_100 |
| FC12 | 0 | 2 | 0 | 1.617 | 90.5% | AHU_1 |
| AVG-ZONE-TEMP | 126 | 0 | 1 | 0.000 | - | - |
| FAULT-ELAPSED-HOURS | 84 | 0 | 1 | 0.000 | - | - |
| ECON-1 | 2 | 0 | 0 | 0.000 | - | - |
| FC7 | 0 | 0 | 2 | 0.000 | - | - |
| FC1 | 2 | 0 | 0 | 0.000 | - | - |
| FAN-RUNTIME-HOURS | 4 | 0 | 3 | 0.000 | - | - |
| ZONE-COMFORT-PCT | 42 | 0 | 1 | 0.000 | - | - |
| ECON-5 | 0 | 0 | 2 | 0.000 | - | - |
| FC3 | 2 | 0 | 0 | 0.000 | - | - |
| FC11 | 2 | 0 | 0 | 0.000 | - | - |
| OAT-METEO | 4 | 0 | 0 | 0.000 | - | - |
| ECON-4 | 2 | 0 | 0 | 0.000 | - | - |

## Summary by equipment (failures only)

| equipment | failed rules | fail metrics | max Δ |
| --- | --- | ---: | ---: |
| AHU_1 | ECON-2, FC10, FC12, FC13-SAT-HIGH, FC2, FC8, FC9 | 7 | 29.767 |
| AHU_2 | ECON-2, FC10, FC12, FC13-SAT-HIGH, FC2, FC8, FC9 | 7 | 26.000 |
| VAVFC_100 | VAV-1 | 1 | 6.800 |
| VAVH_115 | VAV-1 | 1 | 4.333 |
| VAV_3 | VAV-1 | 1 | 3.800 |
| VAV_25 | VAV-1 | 1 | 3.467 |
| VAV_30 | VAV-1 | 1 | 3.417 |
| VAV_23 | VAV-1 | 1 | 3.133 |
| VAV_32 | VAV-1 | 1 | 3.100 |
| VAV_17 | VAV-1 | 1 | 2.850 |
| VAV_26 | VAV-1 | 1 | 2.233 |
| VAV_24 | VAV-1 | 1 | 2.133 |
| VAV_18 | VAV-1 | 1 | 2.083 |
| VAV_1 | VAV-1 | 1 | 1.833 |
| VAV_9 | VAV-1 | 1 | 1.767 |
| VAV_21 | VAV-1 | 1 | 1.583 |
| VAV_28 | VAV-1 | 1 | 1.500 |
| VAV_29 | VAV-1 | 1 | 1.500 |
| VAV_27 | VAV-1 | 1 | 1.467 |
| VAV_8 | VAV-1 | 1 | 1.450 |
| VAV_33 | VAV-1 | 1 | 1.450 |
| VAV_113 | VAV-1 | 1 | 1.417 |
| VAV_12 | VAV-1 | 1 | 1.383 |
| VAV_2 | VAV-1 | 1 | 1.250 |
| VAV_7 | VAV-1 | 1 | 1.217 |
| VAV_114 | VAV-1 | 1 | 1.183 |
| VAV_22 | VAV-1 | 1 | 1.150 |
| VAV_106 | VAV-1 | 1 | 0.967 |
| VAV_108 | VAV-1 | 1 | 0.967 |
| VAV_4 | VAV-1 | 1 | 0.933 |

## Top 20 mismatches (absolute delta)

| rule | equipment | metric | python | sql | delta | pct |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| FC8 | AHU_1 | fault_hours | 1461.900 | 1491.667 | 29.767 | 2.0% |
| FC8 | AHU_2 | fault_hours | 1541.000 | 1567.000 | 26.000 | 1.7% |
| FC13-SAT-HIGH | AHU_2 | fault_hours | 350.900 | 371.917 | 21.017 | 6.0% |
| FC10 | AHU_2 | fault_hours | 516.300 | 536.583 | 20.283 | 3.9% |
| FC2 | AHU_2 | fault_hours | 317.500 | 335.167 | 17.667 | 5.6% |
| FC9 | AHU_2 | fault_hours | 1506.700 | 1524.250 | 17.550 | 1.2% |
| FC10 | AHU_1 | fault_hours | 788.500 | 804.750 | 16.250 | 2.1% |
| FC13-SAT-HIGH | AHU_1 | fault_hours | 292.600 | 303.917 | 11.317 | 3.9% |
| ECON-2 | AHU_2 | fault_hours | 1433.700 | 1425.417 | 8.283 | 0.6% |
| ECON-2 | AHU_1 | fault_hours | 1093.000 | 1085.583 | 7.417 | 0.7% |
| VAV-1 | VAVFC_100 | fault_hours | 1524.200 | 1531.000 | 6.800 | 0.4% |
| FC9 | AHU_1 | fault_hours | 628.600 | 635.083 | 6.483 | 1.0% |
| FC2 | AHU_1 | fault_hours | 20.000 | 24.917 | 4.917 | 24.6% |
| VAV-1 | VAVH_115 | fault_hours | 185.500 | 189.833 | 4.333 | 2.3% |
| VAV-1 | VAV_3 | fault_hours | 206.200 | 210.000 | 3.800 | 1.8% |
| VAV-1 | VAV_25 | fault_hours | 389.700 | 393.167 | 3.467 | 0.9% |
| VAV-1 | VAV_30 | fault_hours | 174.000 | 177.417 | 3.417 | 2.0% |
| VAV-1 | VAV_23 | fault_hours | 338.700 | 341.833 | 3.133 | 0.9% |
| VAV-1 | VAV_32 | fault_hours | 65.400 | 68.500 | 3.100 | 4.7% |
| VAV-1 | VAV_17 | fault_hours | 145.900 | 148.750 | 2.850 | 2.0% |

## Top 20 mismatches (percent delta)

| rule | equipment | metric | python | sql | delta | pct |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| FC12 | AHU_2 | fault_hours | 1.400 | 2.667 | 1.267 | 90.5% |
| FC2 | AHU_1 | fault_hours | 20.000 | 24.917 | 4.917 | 24.6% |
| FC12 | AHU_1 | fault_hours | 15.800 | 17.417 | 1.617 | 10.2% |
| FC13-SAT-HIGH | AHU_2 | fault_hours | 350.900 | 371.917 | 21.017 | 6.0% |
| FC2 | AHU_2 | fault_hours | 317.500 | 335.167 | 17.667 | 5.6% |
| VAV-1 | VAV_32 | fault_hours | 65.400 | 68.500 | 3.100 | 4.7% |
| FC10 | AHU_2 | fault_hours | 516.300 | 536.583 | 20.283 | 3.9% |
| FC13-SAT-HIGH | AHU_1 | fault_hours | 292.600 | 303.917 | 11.317 | 3.9% |
| VAV-1 | VAV_15 | fault_hours | 27.500 | 28.417 | 0.917 | 3.3% |
| VAV-1 | VAV_18 | fault_hours | 67.000 | 69.083 | 2.083 | 3.1% |
| VAV-1 | VAV_7 | fault_hours | 42.200 | 43.417 | 1.217 | 2.9% |
| VAV-1 | VAV_106 | fault_hours | 37.700 | 38.667 | 0.967 | 2.6% |
| VAV-1 | VAV_108 | fault_hours | 37.700 | 38.667 | 0.967 | 2.6% |
| VAV-1 | VAVH_115 | fault_hours | 185.500 | 189.833 | 4.333 | 2.3% |
| VAV-1 | VAV_16 | fault_hours | 31.200 | 31.917 | 0.717 | 2.3% |
| VAV-1 | VAV_8 | fault_hours | 64.800 | 66.250 | 1.450 | 2.2% |
| VAV-1 | VAV_114 | fault_hours | 55.400 | 56.583 | 1.183 | 2.1% |
| FC10 | AHU_1 | fault_hours | 788.500 | 804.750 | 16.250 | 2.1% |
| FC8 | AHU_1 | fault_hours | 1461.900 | 1491.667 | 29.767 | 2.0% |
| VAV-1 | VAV_33 | fault_hours | 73.800 | 75.250 | 1.450 | 2.0% |

## Proven parity

- `AVG-ZONE-TEMP`
- `FAULT-ELAPSED-HOURS`
- `ECON-1`
- `FC1`
- `FAN-RUNTIME-HOURS`
- `ZONE-COMFORT-PCT`
- `FC3`
- `FC11`
- `OAT-METEO`
- `ECON-4`

## Near parity

_None._

## Material mismatch

- `FC8`
- `FC13-SAT-HIGH`
- `FC10`
- `FC2`
- `FC9`
- `ECON-2`
- `VAV-1`
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

## All mismatches

| rule | equipment | metric | python | sql | delta | pct |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| FC8 | AHU_2 | fault_hours | 1541.000 | 1567.000 | 26.000 | 1.7% |
| FC9 | AHU_1 | fault_hours | 628.600 | 635.083 | 6.483 | 1.0% |
| VAV-1 | VAV_17 | fault_hours | 145.900 | 148.750 | 2.850 | 2.0% |
| VAV-1 | VAV_2 | fault_hours | 75.000 | 76.250 | 1.250 | 1.7% |
| VAV-1 | VAV_23 | fault_hours | 338.700 | 341.833 | 3.133 | 0.9% |
| VAV-1 | VAV_8 | fault_hours | 64.800 | 66.250 | 1.450 | 2.2% |
| VAV-1 | VAV_19 | fault_hours | 45.700 | 46.250 | 0.550 | 1.2% |
| VAV-1 | VAV_7 | fault_hours | 42.200 | 43.417 | 1.217 | 2.9% |
| VAV-1 | VAV_4 | fault_hours | 61.400 | 62.333 | 0.933 | 1.5% |
| VAV-1 | VAV_9 | fault_hours | 204.900 | 206.667 | 1.767 | 0.9% |
| VAV-1 | VAV_24 | fault_hours | 283.700 | 285.833 | 2.133 | 0.8% |
| VAV-1 | VAV_18 | fault_hours | 67.000 | 69.083 | 2.083 | 3.1% |
| FC13-SAT-HIGH | AHU_1 | fault_hours | 292.600 | 303.917 | 11.317 | 3.9% |
| FC9 | AHU_2 | fault_hours | 1506.700 | 1524.250 | 17.550 | 1.2% |
| FC12 | AHU_2 | fault_hours | 1.400 | 2.667 | 1.267 | 90.5% |
| VAV-1 | VAV_26 | fault_hours | 190.100 | 192.333 | 2.233 | 1.2% |
| VAV-1 | VAV_27 | fault_hours | 230.200 | 231.667 | 1.467 | 0.6% |
| VAV-1 | VAV_1 | fault_hours | 152.500 | 154.333 | 1.833 | 1.2% |
| VAV-1 | VAV_3 | fault_hours | 206.200 | 210.000 | 3.800 | 1.8% |
| VAV-1 | VAV_106 | fault_hours | 37.700 | 38.667 | 0.967 | 2.6% |
| VAV-1 | VAV_22 | fault_hours | 142.100 | 143.250 | 1.150 | 0.8% |
| VAV-1 | VAV_12 | fault_hours | 100.700 | 102.083 | 1.383 | 1.4% |
| VAV-1 | VAV_114 | fault_hours | 55.400 | 56.583 | 1.183 | 2.1% |
| VAV-1 | VAV_20 | fault_hours | 59.200 | 60.000 | 0.800 | 1.4% |
| VAV-1 | VAV_25 | fault_hours | 389.700 | 393.167 | 3.467 | 0.9% |
| FC2 | AHU_2 | fault_hours | 317.500 | 335.167 | 17.667 | 5.6% |
| FC13-SAT-HIGH | AHU_2 | fault_hours | 350.900 | 371.917 | 21.017 | 6.0% |
| VAV-1 | VAVH_115 | fault_hours | 185.500 | 189.833 | 4.333 | 2.3% |
| VAV-1 | VAV_108 | fault_hours | 37.700 | 38.667 | 0.967 | 2.6% |
| FC8 | AHU_1 | fault_hours | 1461.900 | 1491.667 | 29.767 | 2.0% |
| VAV-1 | VAV_33 | fault_hours | 73.800 | 75.250 | 1.450 | 2.0% |
| FC10 | AHU_2 | fault_hours | 516.300 | 536.583 | 20.283 | 3.9% |
| FC12 | AHU_1 | fault_hours | 15.800 | 17.417 | 1.617 | 10.2% |
| VAV-1 | VAV_14 | fault_hours | 72.700 | 73.250 | 0.550 | 0.8% |
| VAV-1 | VAV_30 | fault_hours | 174.000 | 177.417 | 3.417 | 2.0% |
| VAV-1 | VAV_21 | fault_hours | 108.500 | 110.083 | 1.583 | 1.5% |
| ECON-2 | AHU_2 | fault_hours | 1433.700 | 1425.417 | 8.283 | 0.6% |
| VAV-1 | VAV_29 | fault_hours | 276.000 | 277.500 | 1.500 | 0.5% |
| VAV-1 | VAV_16 | fault_hours | 31.200 | 31.917 | 0.717 | 2.3% |
| FC10 | AHU_1 | fault_hours | 788.500 | 804.750 | 16.250 | 2.1% |
| VAV-1 | VAV_32 | fault_hours | 65.400 | 68.500 | 3.100 | 4.7% |
| VAV-1 | VAVFC_100 | fault_hours | 1524.200 | 1531.000 | 6.800 | 0.4% |
| FC2 | AHU_1 | fault_hours | 20.000 | 24.917 | 4.917 | 24.6% |
| VAV-1 | VAV_28 | fault_hours | 222.500 | 224.000 | 1.500 | 0.7% |
| ECON-2 | AHU_1 | fault_hours | 1093.000 | 1085.583 | 7.417 | 0.7% |
| VAV-1 | VAV_15 | fault_hours | 27.500 | 28.417 | 0.917 | 3.3% |
| VAV-1 | VAV_113 | fault_hours | 74.500 | 75.917 | 1.417 | 1.9% |
| VAV-1 | VAVH_109 | fault_hours | 1007.200 | 1007.917 | 0.717 | 0.1% |
