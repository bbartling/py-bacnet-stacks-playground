# Contributing — RL / rleplus backend

vibe22 uses [airboxlab/rllib-energyplus](https://github.com/airboxlab/rllib-energyplus)
as the **EnergyPlus Gym/runner source of truth** (MIT). Amphitheater IDF is **unused**.

Do **not** `pip install` his Poetry extras (Ray RLlib, Pearl). Trainer is **Stable-Baselines3**.

His `rleplus.env.energyplus` calls `try_import_energyplus_api()` at **module import**
(asserts EnergyPlus). CI has no E+, so we **do not import that module**. Lakeside
`EnergyPlusEnv` / `EnergyPlusRunner` keep his Gym API and queue protocol, with
deterministic DualSP defaults (**never** `action_space.sample()`) and six-actuator
+ Electricity:Facility meter-index 0 patches.

| Piece | Where |
| --- | --- |
| Upstream tree | `third_party/rllib-energyplus` or `RLEPLUS_ROOT` |
| Lakeside Gym | `eplus_gym/env.py` |
| Six DualSP send | `eplus_gym/runner.py` |
| Building | **A04** `lakeside_w2a_a04_dual_champion.idf` only |
| Day MDP | `eplus_gym/rl/daily_env.py` — one SB3 step = one LIVE A04 day |
| Ramp gate | `eplus_gym/rl/physics_ramp_gate.py` — BAS p99.9 × 3; **do not raise** to pass A04 |
| Trainer | SB3 PPO/DQN — `--mode full` refused until `ramp_gate.json` `passed=true` |

DSM DualSP recovery must apply `recovery_ramp_minutes` (window = occupancy start minus lead minus ramp). Evening setback remains a step; A04 zone air can follow ~5 °F in 15 min. That is a **model/physics** NO-GO for long RL, not a license to inflate the threshold.

## Product

1. Screening claim: ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY
2. Subprocess isolation: `live_day_worker` (Windows torch + `delete_state`)
3. CLI: `python scripts/vibe22_rl.py campaign --n-days 100 --run-id unique100_rleplus`
