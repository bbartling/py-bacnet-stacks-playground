# Contributing — RL / EnergyPlus gym hygiene

vibe22 borrows the **Gym + threaded `pyenergyplus` queue/callback runner** shape from
[airboxlab/rllib-energyplus](https://github.com/airboxlab/rllib-energyplus).

We do **not** ship Ray/RLlib as the first trainer.

## Mapping to upstream

| Upstream idea | vibe22 |
| --- | --- |
| Abstract Gymnasium env | `eplus_gym/env.py` `EnergyPlusEnv` |
| Threaded runtime + obs/act queues | `eplus_gym/runner.py` |
| Concrete building env | `eplus_gym/envs/lakeside_w2a.py` (six DualSP actuators) |
| Day-level MDP wrapper | `eplus_gym/rl/daily_env.py` |
| Trainer | **Stable-Baselines3** (`eplus_gym/rl/train_sb3.py`) |
| RLlib entry | `eplus_gym/train_rllib.py` — pointer stub only |

## Product differences (intentional)

1. **Day MDP:** one SB3 `step` = one LIVE weather day via `SixZoneDailyController` + `run_controller_episode`, not per-timestep RL writes.
2. **Six DualSP staging:** `DSM_HTG_SP_{1F_A..2F_B}` on staged IDF copies only (champion immutable).
3. **SB3 first:** PPO continuous + DQN discrete; RLlib optional later.
4. **Subprocess isolation:** trainer process holds torch; each LIVE day runs in `eplus_gym/rl/live_day_worker` (Windows: torch + `delete_state` → `0xC0000374`).
5. **Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY — not operational MPC / BACnet / verified savings.
6. **No surrogate RL:** refuse non-`LIVE_ENERGYPLUS` in `scripts/vibe22_rl.py`.

## Agent entrypoints

- Spec: `vibe22_agent_spec/RL_DAILY_DSM.md`
- Skill: `skills/rl-daily-dsm/SKILL.md`
- CLI: `python scripts/vibe22_rl.py train|bakeoff|compare`
- Baseline comparator: `python scripts/vibe22.py optimize-day …`
