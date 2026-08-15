---
name: rl-daily-dsm
description: >-
  LIVE EnergyPlus daily six-zone RL on Lakeside A04. rleplus Gym/runner backend.
  SB3 PPO/DQN. One step = one weather day. No Ray, no Amphitheater IDF.
---

# RL daily DSM (A04 + rleplus)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.

```powershell
python scripts/vibe22_rl.py campaign --n-days 100 --run-id unique100_rleplus --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py campaign --pool year2xsyn --run-id year2xsyn --site-root $env:SITE_ROOT
```

`--pool year2xsyn` = all unique AMY dates plus a synthetic Nov–Mar clone (dry-bulb N(0,2.5°C)). Still LIVE EnergyPlus. Not a second real winter.

One action is selected for an entire weather day (contextual-bandit-like daily policy). DQN Discrete(64) is a coarse ablation, not a PPO bakeoff winner.

[`../../vibe22_agent_spec/CONTRIBUTING_RL.md`](../../vibe22_agent_spec/CONTRIBUTING_RL.md)
