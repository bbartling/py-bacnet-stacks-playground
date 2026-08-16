---
name: rl-daily-dsm
description: >-
  LIVE EnergyPlus daily six-zone RL on Lakeside A04. rleplus Gym/runner backend.
  SB3 PPO/DQN. One step = one weather day. No Ray, no Amphitheater IDF.
  Long campaign forbidden while physics-ramp gate is failed.
---

# RL daily DSM (A04 + rleplus)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.

**Do not** start a 20–30 hour PPO/DQN campaign while
`docs/audits/figures/postfix/ramp_gate.json` has `passed: false`.
Reproduce: `python scripts/reproduce_physics_ramp_gate.py` (exit 4 = still NO-GO).
Do not raise `ENGINEERING_MARGIN`. Do not retune A04 solely to pass the ramp gate.

Operator-pay smoke (`operator_pay_2x_v1`) is untrained policies on three engineering-gate days — **not** learning evidence, **no winner**. Random policy is i.i.d., not a random walk. January is not a pristine holdout.

```powershell
python scripts/vibe22_rl.py operator-pay-experiment --mode smoke --reward-name operator_pay_2x_v1 --run-id oppay2x_smoke_20260816 --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py campaign --n-days 100 --run-id unique100_rleplus --site-root $env:SITE_ROOT
```

`--pool year2xsyn` is historical TRAIN only (not eval). Still LIVE EnergyPlus. Not a second real winter.

One action is selected for an entire weather day (contextual-bandit-like daily policy). DQN Discrete(64) is a coarse ablation, not a PPO bakeoff winner.

[`../../vibe22_agent_spec/CONTRIBUTING_RL.md`](../../vibe22_agent_spec/CONTRIBUTING_RL.md)
