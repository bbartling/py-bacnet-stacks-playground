# RL daily six-zone DSM (LIVE EnergyPlus)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY

Not operational MPC. Not verified savings. Not BACnet.

## Locked MDP

| Item | Value |
| --- | --- |
| Episode | One weather day (96 × 15-min) |
| Simulator | `LIVE_ENERGYPLUS` only |
| Action | Daily setpoints + HVAC/occupancy timing → `SixZoneDailyParams` |
| School start | 08:00 = step **32** |
| Reward | `-(C_energy + C_peak) - λ_pre8 * V_pre8 - λ_occ * V_occ` |
| Plots | matplotlib → `reports/eplus_gym/rl/<run_id>/` and [`../plots/rl_report/`](../plots/rl_report/README.md) |
| Trainer | Stable-Baselines3 PPO + DQN |
| Baselines | random walk (uniform action box), cold-morning heuristic, `vibe22.py` coordinate descent |
| Process model | Trainer = torch/SB3; each LIVE day = **subprocess** worker |

## Install

```powershell
pip install -r requirements.txt -r requirements-rl.txt
```

## CLI

```powershell
python scripts/vibe22_rl.py train --algo PPO --days 2026-01-26 --timesteps 6 --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py bakeoff --days 2026-01-26 --timesteps 8 --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py compare --run-id <id> --day 2026-01-26 --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py pretrain --algo PPO --timesteps 20 --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py report --run-id office_pretrain_horizon --random-timesteps 20 --site-root $env:SITE_ROOT
```

Git-visible report: [`../plots/rl_report/`](../plots/rl_report/README.md) (`episodes.csv`, `comparison.json`, PNGs).

## Verdict (2026-08-14 report @ sp_creekside)

| Gate | Status |
| --- | --- |
| LIVE only | **PASS** (surrogate refused) |
| Unit spaces/reward/isolate/report | **PASS** (pytest) |
| Six-zone actuation | READY (precondition) |
| LIVE PPO office pretrain (`timesteps=20`) | **PASS** `office_pretrain_horizon` mean_reward ≈ −4078, pre8=0 |
| LIVE random_walk (`n=20`) | **PASS** mean_reward ≈ −4182, pre8≈2.1 |
| LIVE heuristic week (`n=7`) | **PASS** mean_reward ≈ −3929 (best mean), pre8=1 |
| Coordinate descent (1 scored day) | mean_reward ≈ −4333 |
| Surrogate / lookup RL | **NO-GO** |

**Do not overhaul** (SAC/A2C/RLlib) yet: the cold-morning heuristic still beats 20-step PPO on mean reward; PPO is better on pre-8 comfort. Next science is more LIVE days or imitating the heuristic, not more algorithms.

Smoke/report rewards are illustrative screening scores only — not verified savings.

Office pretrain pickles `{SITE}/reports/eplus_gym/rl/field_shared/daily_policy.pkl`.
Field sidecar (pretend BACnet docker) loads that pack + midnight 24h hourly
forecast (EPW replay = pretend OpenWeatherMap) and writes advisory JSON only.

Artifacts: `{SITE}/reports/eplus_gym/rl/<run_id>/` (models, episodes, plots, summaries).

## Hygiene (rllib-energyplus shape)

- Gym: `observation_space` / `action_space`, `reset` → `(obs, info)`, `step` → `(obs, reward, terminated, truncated, info)`
- LIVE day via EnergyPlus Python API callbacks (`LakesideW2AEnv` + `run_controller_episode`)
- Shipped trainer: SB3 (`eplus_gym/rl/train_sb3.py`). `eplus_gym/train_rllib.py` is a pointer stub only.
- **Isolation:** `eplus_gym/rl/live_day_worker.py` — torch + `delete_state` heap-corrupts in-process on Windows (`0xC0000374`); RL defaults `isolate_eplus=True`.

Build plan: [`RL_DAILY_SIX_ZONE_BUILD_PLAN.md`](RL_DAILY_SIX_ZONE_BUILD_PLAN.md).  
Skill: [`../skills/rl-daily-dsm/SKILL.md`](../skills/rl-daily-dsm/SKILL.md).
