# Vibe22 — Lakeside A04 daily RL (rllib-shaped local runner)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY  
Not Amphitheater. Not Ray. Not A05. Champion: `lakeside_w2a_a04_dual_champion.idf`.

Gym/runner is **rllib-shaped and local** (`eplus_gym`). Pin generic helpers to rllib-energyplus `feat/generic-runner` @ `01c5dc7`. Not a thin wrapper yet.

**Physics-ramp / A04-v2 (2026-08-16):** CapMult≥28 passes ramp but fails frozen Jan peak ±10% of 284.82 kW; InternalMass alone does not fix DualSP tracking. Verdict: `NO_GO_LONG_RL_TRAINING_TRANSIENT_MODEL_NOT_VALIDATED`. Audit: [`docs/audits/2026-08-16-vibe22-a04v2-transient-nogo.md`](docs/audits/2026-08-16-vibe22-a04v2-transient-nogo.md).

**2026-08-18 final physics + research PoC:** Terminal **B**. No champion. Track B LIVE matrix **2,106 scored / 5,332 warmup** (37 reports). CLI instrumented Track B **738 / 4,657** plus active invalid-domain **759**. Track C sequential failed W2A=0. Long RL remains blocked. Bounded A04 `research-poc` is labeled `SIMULATION-ONLY RESEARCH POC`, not `SIMULATION_TRAINING_READY`. Audit: [`docs/audits/2026-08-18-vibe22-final-physics-and-rl-poc.md`](docs/audits/2026-08-18-vibe22-final-physics-and-rl-poc.md).

**Physics-ramp gate (A04 parent):** still FAIL on evening DualSP — [`docs/audits/2026-08-16-vibe22-physics-ramp-nogo.md`](docs/audits/2026-08-16-vibe22-physics-ramp-nogo.md).

## Where results live

| Path | Meaning |
| --- | --- |
| Site `reports/eplus_gym/rl/year2xsyn` | Frozen historical TRAIN (1951 E+ logs, 2 Severe/run) |
| [`plots/rl_report_year2x/`](plots/rl_report_year2x/README.md) | Git snapshot; **winner=null** |
| [`plots/rl_report/`](plots/rl_report/README.md) | LEGACY unique-100 TRAIN exploration |
| [`plots/rl_report_operator_pay/`](plots/rl_report_operator_pay/README.md) | operator_pay_2x **smoke** (untrained; no winner) |
| [`reports/`](reports/STALE_PRE_RL_README.md) | STALE pre-RL |
| [`docs/audits/2026-08-15-vibe22-rl-scientific-validity-and-roadmap.md`](docs/audits/2026-08-15-vibe22-rl-scientific-validity-and-roadmap.md) | Validity report |
| [`docs/audits/figures/postfix/ramp_gate.json`](docs/audits/figures/postfix/ramp_gate.json) | Ramp gate (`passed=false`) |

```powershell
pip install -r requirements.txt -r requirements-rl.txt
python -m pytest tests -q
python scripts/reproduce_physics_ramp_gate.py
python scripts/build_vibe22_rl_validity_report.py --site-root $env:SITE_ROOT
```
