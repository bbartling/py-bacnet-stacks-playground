---
name: nightly-grid-compute
description: >-
  Identical-state nightly A04 EnergyPlus grid-search compute benchmark on a
  single cold school day. Measures wall/CPU/memory vs candidate budgets.
  No RL training. No BACnet. Use when running or publishing nightly_grid_compute.
---

# Nightly A04 grid-search compute benchmark

**Claim:** SIMULATION-ONLY RESEARCH · RETROSPECTIVE WEATHER BENCHMARK · NO BACNET.

## Hard rules

- Do **not** train PPO/DQN
- Do **not** issue BACnet commands
- Do **not** modify A04 physics / create A05
- Do **not** soften 15/30 minute deadlines after seeing results
- Selection = lowest-cost **fully-ready** candidate (not RL training reward)

## CLI

```powershell
py -3.12 scripts/vibe22_nightly_grid_compute.py --site-root $env:SITE_ROOT --stage freeze
py -3.12 scripts/vibe22_nightly_grid_compute.py --site-root $env:SITE_ROOT --site-run-dir <DIR> --stage all --resume
```

## Pack

`docs/results/nightly_grid_compute/`
