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
```

SoT: [`../../vibe22_agent_spec/RL_DAILY_DSM.md`](../../vibe22_agent_spec/RL_DAILY_DSM.md) ·
[`../../vibe22_agent_spec/CONTRIBUTING_RL.md`](../../vibe22_agent_spec/CONTRIBUTING_RL.md)
