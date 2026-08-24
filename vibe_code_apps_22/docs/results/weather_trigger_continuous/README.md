# Weather-triggered continuous-conditioning grid experiment

> Realized EPW outdoor temperatures drive retrospective midnight-only daily policy selection
> (`RETROSPECTIVE_WEATHER_POLICY_SCREEN`). Modeled costs are illustrative. Continuous 68/74
> actuates heating at 68°F all day; cooling remains fixed ~74/85°F thermostatic schedules.

## Public labels

- `SIMULATION-ONLY RESEARCH`
- `A04 IS NOT A TRANSIENT-VALIDATED PHYSICS CHAMPION`
- `ILLUSTRATIVE COSTS`
- `RETROSPECTIVE_WEATHER_POLICY_SCREEN`
- `NO BACNET COMMAND AUTHORITY`

## Research conclusion

**`WEATHER_TRIGGER_IMPROVES_PEAK_WITH_ENERGY_PENALTY`** — no operational winner.

- Best economic strategy (illustrative FLAT): `ALWAYS_GRID_42`
- Lowest-peak / peak-first sensitivity: `ALWAYS_CONTINUOUS_68_74`
- `SIMULATION_TRAINING_READY`: false
- `OPERATIONAL_DSM_READY`: false
- BACnet command authority: **0**

## Scope

- Scored days: 2025-12-01 … 2026-01-31 (62 days, 5,952 intervals per strategy)
- Weather policies LIVE: 9 continuous EnergyPlus processes
- Reference arms imported from two-month replay (not re-run)
- Primary tariff: FLAT_PLUS_DEMAND; secondary TOU re-score

## Artifacts

| File | Role |
| --- | --- |
| `strategy_summary.csv` | P7 metrics per strategy |
| `daily_trigger_log.csv` | Daily decision + 24 hourly OAT °F |
| `flat_cost_table.csv` / `tou_cost_table.csv` | Illustrative costs |
| `peak_first_sensitivity.json` | PEAK_FIRST_RESEARCH_SENSITIVITY |
| `peak_cap_feasibility.csv` | 260/250/240/230 kW caps |
| `research_conclusion.json` | Single research verdict |
| `figures/` | 10 PNG+SVG plots |

## Honesty

- Do not describe illustrative dollars as verified savings.
- Do not claim PPO/DQN were trained on weather-trigger logic.
- Mild/weekend nightly optional days remain NOT_RUN (separate pack).
