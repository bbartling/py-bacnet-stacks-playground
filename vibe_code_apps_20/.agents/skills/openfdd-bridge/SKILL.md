# Skill: openfdd-bridge

Map Open-FDD / Vibe App 19 rule hits into WattLab evidence + MeasureBriefs.

## Operator path

```powershell
# From a vibe19 agent-export directory (export_agent_bundle / agent_afdd.py --out)
python vibe19_bridge.py path/to/export -o .artifacts/bridge.json
# Optional: merge into a building profile
python vibe19_bridge.py path/to/export --profile examples/buildings/madison_office.json -o .artifacts/merged.json
```

Reads `fdd_summary.csv`, `economizer_weather.csv`, optional `motor_weekly.csv`.

## Common maps

| vibe19 rule | ECM class | WattLab measure / patch |
|---|---|---|
| SCHED-247 / SCHED-1 | Schedule align | `ECM-AHU-SCHED-ALIGN` → `fan_avail_occupied_office` |
| AHU-DUCTHI / FC1 / VAV-1 | GL36 fan / VAV-min proxy | `ECM-GL36-AIRSIDE` → `gl36_airside_proxy` |
| MECH-OAT-1 / ECON-3 / ECON-6 | Low-OAT chiller lockout | `ECM-CHILLER-LOCKOUT` → `chiller_lockout` |
| economizer `prohibited_mech_hours_below_60f` | Reinforces lockout | same |

## Rules

- Evidence first; bridge auto-sets `review_status=approved` for screening UX but still carry confidence flags
- Tag measures `source=vibe19` and record `field_sources`
- Schedule before airside GL36 when both apply (bridge sorts in that order)
- vibe19 does **not** export floor area / climate / rates — those stay user/defaults in WattLab form
