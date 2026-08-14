# Vibe22 — Lakeside A04 daily RL (rleplus backend)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY  
Not Amphitheater. Not Ray. Not A05. Champion: `lakeside_w2a_a04_dual_champion.idf`.

Gym/runner: [airboxlab/rllib-energyplus](https://github.com/airboxlab/rllib-energyplus) via submodule `third_party/rllib-energyplus`. Trainer: SB3.

```powershell
pip install -r requirements.txt -r requirements-rl.txt
python scripts/vibe22_rl.py campaign --n-days 100 --run-id unique100_rleplus --site-root $env:SITE_ROOT
```

Plots: [`plots/rl_report/`](plots/rl_report/README.md)
