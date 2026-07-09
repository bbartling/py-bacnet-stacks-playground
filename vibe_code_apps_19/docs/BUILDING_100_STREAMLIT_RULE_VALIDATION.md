# BUILDING_100 Streamlit rule validation

- Building: **BUILDING_100**
- Equipment: **48**
- Canonical rules: **50**
- Total rule/equipment evaluations: **2400**

## Status counts

| Status | Count |
| --- | ---: |
| PASS | 121 |
| FAULT | 215 |
| SKIPPED_MISSING_ROLES | 187 |
| NOT_APPLICABLE_EQUIPMENT_TYPE | 1877 |
| ERROR | 0 |

## Top missing roles

- `oa_t`: 43
- `vav_disch_t`: 43
- `min_flow_sp`: 43
- `reheat_valve_pct`: 26
- `damper_pct`: 22
- `vav_inlet_t`: 12
- `htg_valve_pct`: 8
- `chw_supply_t`: 6
- `chw_pump_cmd`: 6
- `wx_oa_t`: 4
- `any sensor role from sweep list`: 4
- `zone_flow`: 4
- `vav_total_flow`: 2
- `clg_coil_enter_t`: 2
- `clg_coil_leave_t`: 2

## Top faults

- **SV-RANGE** / VAV_7: 2631.42h
- **VAV-1** / VAV_7: 2631.25h
- **SV-FLATLINE** / VAV_7: 2630.5h
- **SV-STALE** / VAV_7: 2629.5h
- **SV-FLATLINE** / CHILLER_2: 2627.58h
- **SV-FLATLINE** / CHILLER_1: 2627.5h
- **SV-FLATLINE** / BOILERS_PUMPS: 2624.83h
- **SV-STALE** / CHILLER_2: 2623.58h
- **SV-STALE** / CHILLER_1: 2623.5h
- **SV-STALE** / BOILERS_PUMPS: 2618.83h
- **SV-FLATLINE** / VAVH_109: 2223.17h
- **SV-STALE** / VAVH_109: 2045.92h
- **SV-FLATLINE** / VAV_107: 1929.33h
- **SV-FLATLINE** / VAV_26: 1854.92h
- **AHU-SATDEV** / AHU_2: 1794.58h

## Limitations

- Role map YAML covers demo equipment; many VAV/plant rules skip until roles are mapped.
- OAT-METEO / ECON-3 need weather columns merged from `weather/history_wide.csv`.
- Equipment kind inference is heuristic (AHU/VAV/chiller/boiler/weather).