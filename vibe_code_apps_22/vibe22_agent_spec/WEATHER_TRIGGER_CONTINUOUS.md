# Weather-triggered continuous-conditioning — agent spec

**Purpose:** Bounded Dec 2025–Jan 2026 LIVE EnergyPlus retrospective screen of
midnight-only weather-triggered hybrid policies (continuous 68/74 vs discrete_114)
without retraining PPO/DQN.

**Claim boundary:** `RETROSPECTIVE_WEATHER_POLICY_SCREEN` · ILLUSTRATIVE COSTS ·
NO BACNET COMMAND AUTHORITY · A04 NOT TRANSIENT-VALIDATED.

## Continuous 68/74 meaning

- Heating thermostat limit = 68°F for all 96 intervals (`continuous_params(68.0)`)
- Cooling ≈ 74°F occupied / 85°F unoccupied via fixed `cooling_schedule_f` (not RL-actuated)
- HVAC remains thermostatically controlled; compressors are not commanded continuously
- Policy decision once at midnight; no intraday switching

## Policies (9 LIVE)

| ID | Rule |
| --- | --- |
| ALWAYS_GRID_114 / 42 / 43 | Fixed discrete indices |
| ALWAYS_CONTINUOUS_68_74 | Continuous 68/74 every day |
| COLD_TRIGGER_10F / 20F / 30F | Min hourly OAT ≤ threshold → continuous else discrete_114 |
| COLD_TRIGGER_20F_4H / 8H | ≥4 / ≥8 hours ≤ 20°F → continuous else discrete_114 |

## Modules

| Module | Role |
| --- | --- |
| `contracts/weather_triggered_continuous_v1.json` | Frozen contract |
| `eplus_gym/rl/weather_trigger_select.py` | Midnight selection + forecast hook |
| `eplus_gym/rl/weather_trigger_replay.py` | ContinuityPlant 62-day runners |
| `eplus_gym/rl/weather_trigger_metrics.py` | Summary, PEAK_FIRST, caps, conclusion |
| `eplus_gym/rl/weather_trigger_figures.py` | 10 figures |
| `eplus_gym/rl/weather_trigger_publish.py` | `docs/results/weather_trigger_continuous/` |
| `scripts/vibe22_weather_trigger_replay.py` | CLI |

## Weather honesty

Uses **realized EPW** outdoor temperatures. Do not call realized weather a forecast.
Store 24 hourly OAT °F per daily decision in `daily_trigger_log.csv`.

## Execution

```powershell
$env:SITE_ROOT = "C:\path\to\site"
py -3.12 scripts/vibe22_weather_trigger_replay.py --strategy all `
  --two-month-site-run $env:SITE_ROOT/reports/eplus_gym/rl/two_month_replay_<stamp>
```

BACnet command authority = 0. Do not merge without human auth.
