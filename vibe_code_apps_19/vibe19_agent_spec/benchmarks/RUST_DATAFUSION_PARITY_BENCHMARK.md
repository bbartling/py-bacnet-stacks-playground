# Rust + DataFusion parity benchmark

Generated: 2026-07-09 12:59 UTC

- building: `BUILDING_100`
- tolerance: `0.5`
- rules compared: 19
- equipment compared: 48
- pass: 234
- fail: 46
- skipped (missing roles): 11
- python-only keys: 250
- sql-only keys: 616
- max abs delta: 1147.4167
- max pct delta: 5737.08%
- material failure: true

## Mismatches

| rule | equipment | metric | python | sql | delta | pct |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| VAV-1 | VAV_113 | fault_hours | 74.500 | 75.917 | 1.417 | 1.9% |
| VAV-1 | VAV_18 | fault_hours | 123.800 | 124.833 | 1.033 | 0.8% |
| VAV-1 | VAV_16 | fault_hours | 22.200 | 22.750 | 0.550 | 2.5% |
| FC12 | AHU_2 | fault_hours | 1.400 | 0.000 | 1.400 | 100.0% |
| VAV-1 | VAV_8 | fault_hours | 366.000 | 370.083 | 4.083 | 1.1% |
| VAV-1 | VAV_19 | fault_hours | 123.800 | 124.833 | 1.033 | 0.8% |
| VAV-1 | VAVFC_100 | fault_hours | 1524.200 | 1531.000 | 6.800 | 0.4% |
| ECON-4 | AHU_2 | fault_hours | 360.600 | 365.917 | 5.317 | 1.5% |
| ECON-2 | AHU_2 | fault_hours | 1433.700 | 1425.417 | 8.283 | 0.6% |
| FC2 | AHU_2 | fault_hours | 317.500 | 335.167 | 17.667 | 5.6% |
| FC3 | AHU_1 | fault_hours | 0.000 | 52.500 | 52.500 | 100.0% |
| ECON-2 | AHU_1 | fault_hours | 1093.000 | 1085.583 | 7.417 | 0.7% |
| VAV-1 | VAVH_115 | fault_hours | 185.500 | 189.833 | 4.333 | 2.3% |
| VAV-1 | VAV_21 | fault_hours | 228.600 | 230.667 | 2.067 | 0.9% |
| VAV-1 | VAV_108 | fault_hours | 37.700 | 38.667 | 0.967 | 2.6% |
| ECON-4 | AHU_1 | fault_hours | 464.800 | 445.500 | 19.300 | 4.2% |
| OAT-METEO | AHU_2 | fault_hours | 1086.600 | 1119.333 | 32.733 | 3.0% |
| FC10 | AHU_2 | fault_hours | 516.300 | 536.583 | 20.283 | 3.9% |
| VAV-1 | VAV_1 | fault_hours | 16.200 | 16.750 | 0.550 | 3.4% |
| FC13-SAT-HIGH | AHU_1 | fault_hours | 292.600 | 0.000 | 292.600 | 100.0% |
| VAV-1 | VAV_10 | fault_hours | 1272.600 | 1279.917 | 7.317 | 0.6% |
| VAV-1 | VAV_106 | fault_hours | 37.700 | 38.667 | 0.967 | 2.6% |
| VAV-1 | VAV_114 | fault_hours | 55.400 | 56.583 | 1.183 | 2.1% |
| OAT-METEO | AHU_2 | fault_pct | 41.290 | 42.537 | 1.247 | 3.0% |
| VAV-1 | VAV_11 | fault_hours | 211.600 | 213.000 | 1.400 | 0.7% |
| VAV-1 | VAV_20 | fault_hours | 163.200 | 164.917 | 1.717 | 1.1% |
| FC10 | AHU_1 | fault_hours | 788.500 | 923.500 | 135.000 | 17.1% |
| FC12 | AHU_1 | fault_hours | 15.800 | 862.333 | 846.533 | 5357.8% |
| VAV-1 | VAV_22 | fault_hours | 636.100 | 637.667 | 1.567 | 0.2% |
| VAV-1 | VAV_3 | fault_hours | 110.900 | 114.750 | 3.850 | 3.5% |
| OAT-METEO | AHU_1 | fault_hours | 285.400 | 307.833 | 22.433 | 7.9% |
| VAV-1 | VAV_13 | fault_hours | 58.700 | 59.333 | 0.633 | 1.1% |
| OAT-METEO | AHU_1 | fault_pct | 10.850 | 11.698 | 0.848 | 7.8% |
| VAV-1 | VAV_2 | fault_hours | 75.000 | 76.250 | 1.250 | 1.7% |
| VAV-1 | VAV_23 | fault_hours | 239.800 | 241.833 | 2.033 | 0.8% |
| FC9 | AHU_2 | fault_hours | 1506.700 | 1089.167 | 417.533 | 27.7% |
| FC8 | AHU_2 | fault_hours | 1541.000 | 1721.583 | 180.583 | 11.7% |
| VAV-1 | VAV_24 | fault_hours | 239.800 | 241.833 | 2.033 | 0.8% |
| FC11 | AHU_2 | fault_hours | 0.000 | 1.000 | 1.000 | 100.0% |
| VAV-1 | VAV_12 | fault_hours | 82.100 | 82.833 | 0.733 | 0.9% |
| FC13-SAT-HIGH | AHU_2 | fault_hours | 350.900 | 0.000 | 350.900 | 100.0% |
| VAV-1 | VAV_9 | fault_hours | 204.900 | 206.667 | 1.767 | 0.9% |
| FC8 | AHU_1 | fault_hours | 1461.900 | 1636.333 | 174.433 | 11.9% |
| VAV-1 | VAVH_109 | fault_hours | 1007.200 | 1007.917 | 0.717 | 0.1% |
| FC9 | AHU_1 | fault_hours | 628.600 | 635.167 | 6.567 | 1.0% |
| FC2 | AHU_1 | fault_hours | 20.000 | 1167.417 | 1147.417 | 5737.1% |

## Skipped (missing roles)

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
