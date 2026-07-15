# Skill: openfdd-bridge

Map Open-FDD / Vibe App 19 rule hits into WattLab evidence + MeasureBriefs.

## Common maps

| vibe19 rule | ECM class | WattLab patch |
|---|---|---|
| SCHED-247 | Schedule align | `fan_avail_occupied_office` |
| AHU-DUCTHI / high SP | GL36 fan proxy | `gl36_airside_proxy` |
| VAV high minimums | VAV-min | `gl36_airside_proxy` |

## Rules

- Evidence first; never auto-approve savings
- Carry `equipment_id` and confidence
- Schedule before airside GL36 when both apply
