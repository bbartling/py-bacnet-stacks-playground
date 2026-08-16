# AGENTS.md — Vibe 22 RL-only (A04 + rllib-shaped local runner)

LIVE six-zone daily RL on **Lakeside A04 dual champion**. Product Gym is local
`eplus_gym` (not a thin rllib wrapper). Generic helpers pin to rllib-energyplus
`feat/generic-runner` @ `01c5dc7`. Trainer: **Stable-Baselines3**. No Ray, no Amphitheater IDF.
Do not overwrite `year2xsyn` site artifacts.

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.

**Long campaign:** **FORBIDDEN** while
[`docs/audits/figures/postfix/ramp_gate.json`](docs/audits/figures/postfix/ramp_gate.json)
has `passed: false` (`NO_GO_LONG_RL_TRAINING_PHYSICS_RAMP_IMPLAUSIBLE`).
Do not raise the BAS p99.9 × 3 threshold. Do not retune A04 just to pass the gate.
See [`docs/audits/2026-08-16-vibe22-physics-ramp-nogo.md`](docs/audits/2026-08-16-vibe22-physics-ramp-nogo.md).

Read: [`vibe22_agent_spec/RL_DAILY_DSM.md`](vibe22_agent_spec/RL_DAILY_DSM.md) ·
[`vibe22_agent_spec/CONTRIBUTING_RL.md`](vibe22_agent_spec/CONTRIBUTING_RL.md) ·
[`skills/rl-daily-dsm/SKILL.md`](skills/rl-daily-dsm/SKILL.md)

```powershell
$env:SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
python scripts/vibe22_rl.py operator-pay-experiment --mode smoke --reward-name operator_pay_2x_v1 --run-id oppay2x_smoke_20260816 --site-root $env:SITE_ROOT
python scripts/reproduce_physics_ramp_gate.py
```

`--mode full` must exit 4 until a **newly generated** ramp artifact has `passed=true`.

Non-RL DSM/GL14/Streamlit: [`archive/2026-08-14_pre_rl_only/`](archive/2026-08-14_pre_rl_only/).
Do not restore `archive/2026-08-10_pre_eplus_gym`.
