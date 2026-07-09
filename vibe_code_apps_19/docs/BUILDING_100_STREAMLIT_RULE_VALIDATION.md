# BUILDING_100 Streamlit rule validation

- Building: **BUILDING_100**
- Equipment: **48**
- Canonical rules: **50**
- Total rule/equipment evaluations: **2400**

## Status counts

| Status | Count |
| --- | ---: |
| PASS | 2 |
| FAULT | 11 |
| SKIPPED | 2387 |
| ERROR | 0 |

## Top missing roles

- `any sensor role from sweep list`: 180
- `damper_pct`: 86
- `zone_flow`: 86
- `reheat_valve_pct`: 84
- `oa_t`: 43
- `vav_disch_t`: 43
- `vav_inlet_t`: 43
- `min_flow_sp`: 43
- `zone_t`: 42
- `oa_damper_pct`: 26
- `clg_valve_pct`: 24
- `mat`: 22
- `sat_sp`: 14
- `rat`: 12
- `htg_valve_pct`: 8

## Top faults

- **SV-FLATLINE** / VAV_7: 1490.92h
- **SV-STALE** / VAV_7: 1077.42h
- **SV-FLATLINE** / AHU_1: 570.0h
- **SV-FLATLINE** / AHU_2: 465.33h
- **SV-STALE** / AHU_1: 181.5h
- **SV-STALE** / AHU_2: 180.83h
- **VAV-1** / VAV_7: 42.25h
- **SV-SPIKE** / AHU_1: 0.5h
- **SV-SPIKE** / AHU_2: 0.5h
- **SV-RANGE** / AHU_1: 0.25h
- **SV-RANGE** / AHU_2: 0.25h

## Limitations

- Role map YAML covers demo equipment; many VAV/plant rules skip until roles are mapped.
- OAT-METEO / ECON-3 need weather columns merged from `weather/history_wide.csv`.
- Equipment kind inference is heuristic (AHU/VAV/chiller/boiler/weather).