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
| Trainer | SB3 PPO/DQN |

## Product

1. Screening claim: ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY
2. Subprocess isolation: `live_day_worker` (Windows torch + `delete_state`)
3. CLI: `python scripts/vibe22_rl.py campaign --n-days 100 --run-id unique100_rleplus`
