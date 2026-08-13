---
name: rl-daily-dsm
description: >-
  LIVE EnergyPlus daily six-zone RL screening (Stable-Baselines3 PPO/DQN).
  One SB3 step = one real weather day via SixZoneDailyParams. Matplotlib plots.
  Coordinate-descent baseline via vibe22.py. No surrogates / no BACnet.
  Use when training, bakeoff, compare, or documenting vibe22 RL DSM.
---

# RL daily six-zone DSM (LIVE)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.  
Not operational MPC. Not verified savings. Not BACnet.

**SoT:** [`../../vibe22_agent_spec/RL_DAILY_DSM.md`](../../vibe22_agent_spec/RL_DAILY_DSM.md) ·
[`../../vibe22_agent_spec/CONTRIBUTING_RL.md`](../../vibe22_agent_spec/CONTRIBUTING_RL.md) ·
build plan (SHIPPED): [`../../vibe22_agent_spec/RL_DAILY_SIX_ZONE_BUILD_PLAN.md`](../../vibe22_agent_spec/RL_DAILY_SIX_ZONE_BUILD_PLAN.md)

## Preconditions

1. Six-zone gate READY: `scripts/gate_six_zone_actuation.py`
2. `pip install -r requirements.txt -r requirements-rl.txt`
3. `SITE_ROOT` points at published site pack (practice: `sp_creekside`)

## CLI

```powershell
cd vibe_code_apps_22
$env:SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
python scripts/vibe22_rl.py train --algo PPO --days 2026-01-26 --timesteps 6 --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py bakeoff --days 2026-01-26 --timesteps 8 --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py compare --run-id <id> --day 2026-01-26 --site-root $env:SITE_ROOT
```

Artifacts: `{SITE}/reports/eplus_gym/rl/<run_id>/` (models, episodes, plots, summaries, hashes).

## Locked design

| Item | Value |
| --- | --- |
| Episode | 1 day (96 × 15-min) |
| Action | Daily setpoints + HVAC/occ times → `SixZoneDailyParams` |
| School start | step **32** = 08:00 (cold → penalty) |
| Simulator | `LIVE_ENERGYPLUS` only |
| Plots | matplotlib only |
| Baseline | `scripts/vibe22.py` coordinate descent |
| Isolation | `live_day_worker` subprocess (default) |

## Guardrails

- Never mutate champion IDF / Site Config / BACnet
- Refuse non-LIVE simulators
- No surrogate / farm-lookup “RL”
- Illustrative $ rates ≠ verified savings
- CI covers spaces/reward/isolate unit tests only; LIVE bakeoff is site-local

## Related

- Coordinate descent: [`../eplus-economic-mpc/SKILL.md`](../eplus-economic-mpc/SKILL.md)
- Gym overview: [`../eplus-gym/SKILL.md`](../eplus-gym/SKILL.md)
