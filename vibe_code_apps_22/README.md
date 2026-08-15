# Vibe22 — Lakeside A04 daily RL (rllib-shaped local runner)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY  
Not Amphitheater. Not Ray. Not A05. Champion: `lakeside_w2a_a04_dual_champion.idf`.

Gym/runner is **rllib-shaped and local** (`eplus_gym`). Pin generic helpers to rllib-energyplus `feat/generic-runner` @ `01c5dc7`. Not a thin wrapper yet.

## Where results live

| Path | Meaning |
| --- | --- |
| Site `reports/eplus_gym/rl/year2xsyn` | Frozen historical TRAIN (1951 E+ logs, 2 Severe/run) |
| [`plots/rl_report_year2x/`](plots/rl_report_year2x/README.md) | Git snapshot; **winner=null** |
| [`plots/rl_report/`](plots/rl_report/README.md) | LEGACY unique-100 TRAIN exploration |
| [`reports/`](reports/STALE_PRE_RL_README.md) | STALE pre-RL |
| [`docs/audits/2026-08-15-vibe22-rl-scientific-validity-and-roadmap.md`](docs/audits/2026-08-15-vibe22-rl-scientific-validity-and-roadmap.md) | Validity report |

```powershell
pip install -r requirements.txt -r requirements-rl.txt
python -m pytest tests -q
python scripts/build_vibe22_rl_validity_report.py --site-root $env:SITE_ROOT
```
