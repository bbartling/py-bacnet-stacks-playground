# AHU Economizer FDD — Research Summary

## Purpose

Field-useful economizer diagnostics for RCx/FDD on real BAS historian exports. Rules are deterministic and evidence-based, aligned with public research — not black-box ML.

## Research anchors

| Source | Application |
|--------|-------------|
| **PNNL air-side economizer O&M** | Minimum OA, high-limit lockout, actuator maintenance, sensor placement |
| **California Title 24 JA6.3** | Fault categories: not economizing, economizing when unsuitable, damper stuck, sensor fault |
| **ASHRAE RP-1312 / AHU FDD datasets** | MAT envelope, SAT vs blend, operating-mode oscillation patterns |
| **LBNL FDD public datasets** | Benchmark fault labels for stuck dampers, sensor bias, simultaneous heating/cooling |
| **ASHRAE Guideline 36** | Economizer enable logic, SAT reset, high-limit dry-bulb, minimum OA during occupied |

## Building 100 implementation notes

- **Air-side economizer** on two built-up VAV AHUs with CHW cooling only (no heating coil in export).
- **Available:** OAT, RAT, MAT, SAT, SAT SP (DAT reset), OA damper command (no separate feedback), CHW valve, fan speed/status, OA minimum position.
- **Not available:** OA/RA humidity (enthalpy economizer not evaluated), return/exhaust damper feedback, CO2/DCV, freeze stat, separate economizer enable signal.
- **Damper caveat:** Command percent is used as position proxy — diagnostics warn that % ≠ airflow %.

## Diagnostic hierarchy (implemented)

1. Point mapping & data quality  
2. Sensor plausibility (flatline, range, MAT envelope, weather compare)  
3. Stable occupied AHU operation filter  
4. Damper command/response (stuck, hunting, cmd-only limitation)  
5. Economizer suitability & performance  
6. Energy impact rollups (lost economizer hours, mech cooling during free cool)

## Fault codes

| Code | Name |
|------|------|
| `ECON_SENSOR_FAULT` | Temperature sensor missing/stale/flatline/OOR/MAT implausible |
| `ECON_NOT_ECONOMIZING_WHEN_SHOULD` | Favorable OA + cooling load but damper near minimum |
| `ECON_ECONOMIZING_WHEN_SHOULD_NOT` | Unfavorable OA but damper above minimum |
| `ECON_DAMPER_NOT_MODULATING` | Command varies but no MAT response or flatlined damper |
| `ECON_DAMPER_STUCK_OPEN` | Damper high when should be at minimum |
| `ECON_DAMPER_STUCK_CLOSED` | Damper low when should economize |
| `ECON_EXCESS_OA` | OA above minimum when economizer not suitable |
| `ECON_LOW_OA_VENTILATION_RISK` | OA below minimum during occupied fan operation |
| `ECON_MAT_PLAUSIBILITY` | MAT outside OAT/RAT envelope |
| `ECON_MECH_COOLING_DURING_FREE_COOLING` | CHW active while dry-bulb economizer favorable |

## Known limitations

- 15-minute export interval (5-minute confirmation mapped to 1 sample minimum).
- No enthalpy economizer without humidity points.
- Damper feedback not separate from command — stuck/mismatch detection limited.
- Weather reference is Open-Meteo, not on-site meteorological station.

## References

- PNNL: Air-side economizer operation and maintenance  
- CEC Title 24 JA6.3 economizer FDD  
- ASHRAE RP-1312, Guideline 36  
- LBNL Building FDD toolkit datasets  
- Open-FDD pandas cookbook (MAT envelope, FC8–FC13 economizer rules)
