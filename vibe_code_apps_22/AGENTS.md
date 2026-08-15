# AGENTS.md — Vibe 22 RL-only (A04 + rllib-shaped local runner)

LIVE six-zone daily RL on **Lakeside A04 dual champion**. Product Gym is local
`eplus_gym` (not a thin rllib wrapper). Generic helpers pin to rllib-energyplus
`feat/generic-runner` @ `01c5dc7`. Trainer: **Stable-Baselines3**. No Ray, no Amphitheater IDF.
Do not overwrite `year2xsyn` site artifacts.


**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.

Read: [`vibe22_agent_spec/RL_DAILY_DSM.md`](vibe22_agent_spec/RL_DAILY_DSM.md) ·
[`vibe22_agent_spec/CONTRIBUTING_RL.md`](vibe22_agent_spec/CONTRIBUTING_RL.md) ·
[`skills/rl-daily-dsm/SKILL.md`](skills/rl-daily-dsm/SKILL.md)

```powershell
$env:SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
python scripts/vibe22_rl.py campaign --n-days 100 --run-id unique100_rleplus --site-root $env:SITE_ROOT
```

Non-RL DSM/GL14/Streamlit: [`archive/2026-08-14_pre_rl_only/`](archive/2026-08-14_pre_rl_only/).
Do not restore `archive/2026-08-10_pre_eplus_gym`.
