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
| Plots | matplotlib → `reports/eplus_gym/rl/<run_id>/plots/` |
| Trainer | Stable-Baselines3 PPO + DQN |
| Baseline | `scripts/vibe22.py` coordinate descent |
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
```

Artifacts: `{SITE}/reports/eplus_gym/rl/<run_id>/` (models, episodes, plots, summaries).

## Hygiene (rllib-energyplus shape)

- Gym: `observation_space` / `action_space`, `reset` → `(obs, info)`, `step` → `(obs, reward, terminated, truncated, info)`
- LIVE day via EnergyPlus Python API callbacks (`LakesideW2AEnv` + `run_controller_episode`)
- Shipped trainer: SB3 (`eplus_gym/rl/train_sb3.py`). `eplus_gym/train_rllib.py` is a pointer stub only.
- **Isolation:** `eplus_gym/rl/live_day_worker.py` — torch + `delete_state` heap-corrupts in-process on Windows (`0xC0000374`); RL defaults `isolate_eplus=True`.

## Verdict (2026-08-13 smoke @ sp_creekside)

| Gate | Status |
| --- | --- |
| LIVE only | **PASS** (surrogate refused) |
| Unit spaces/reward/isolate | **PASS** (pytest) |
| Six-zone actuation | READY (precondition) |
| LIVE PPO train (`timesteps=2`) | **PASS** `smoke_ppo_20260126` |
| LIVE PPO+DQN bakeoff | **PASS** `bakeoff_smoke_20260126` (winner DQN @ mean_reward) |
| LIVE compare vs descent | **PASS** (baseline / rl / coordinate_descent rows) |
| Surrogate / lookup RL | **NO-GO** |

Smoke rewards are illustrative screening scores only — not verified savings.
