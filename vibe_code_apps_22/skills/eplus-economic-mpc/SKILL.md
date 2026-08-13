---
name: eplus-economic-mpc
description: >-
  EnergyPlus Gym economic DSM optimization screening (retrospective AMY replay).
  PHYSICAL_ONLY billing-floor objective, six-zone coordinate descent, proposal-only
  recommendations. Never BACnet / never auto-promote Site Config. Streamlit REMOVED.
---

# EnergyPlus Economic MPC (screening)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.
Not operational MPC. Not verified savings. Not live BACnet.

## Cost equations (billing floor)

\[
C = C_{\mathrm{energy}} + C_{\mathrm{demand}}^{\mathrm{inc}}
\]

Default **PHYSICAL_ONLY**: rank by energy / peak / comfort — illustrative $ never
selects a winner. Equations are written into study `report.md` artifacts.

## Workflow

1. Six-zone actuation gate: `scripts/gate_six_zone_actuation.py` → READY.
2. Phase 0 integrity: staged IDF `Sizing Periods=No`; `kind_of_sim==3`; Runtime dates.
3. Controller: `eplus_gym/six_zone_daily_controller.py` (shape `(6,)`).
4. Study CLI:
   `python scripts/vibe22.py optimize-day --day YYYY-MM-DD --lookback-days 3 --budget 64 --no-cache`
5. Approve: `python scripts/vibe22.py approve --study-id …` →
   `approved_recommendation.json` only.

## Optional RL comparator (LIVE only)

After coordinate descent, bake off SB3 PPO/DQN on the same day MDP:

```powershell
pip install -r requirements-rl.txt
python scripts/vibe22_rl.py bakeoff --days 2026-01-26 --timesteps 8 --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py compare --run-id <bakeoff_id> --day 2026-01-26 --site-root $env:SITE_ROOT
```

See [`../rl-daily-dsm/SKILL.md`](../rl-daily-dsm/SKILL.md) · [`../../vibe22_agent_spec/RL_DAILY_DSM.md`](../../vibe22_agent_spec/RL_DAILY_DSM.md).
Coordinate descent remains the non-RL baseline; RL never auto-promotes Site Config.
