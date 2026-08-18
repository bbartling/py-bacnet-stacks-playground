# AGENTS.md — Vibe 22 RL-only (A04 + rllib-shaped local runner)

LIVE six-zone daily RL on **Lakeside A04 dual champion**. Product Gym is local
`eplus_gym` (not a thin rllib wrapper). Generic helpers pin to rllib-energyplus
`feat/generic-runner` @ `01c5dc7`. Trainer: **Stable-Baselines3**. No Ray, no Amphitheater IDF.
Do not overwrite `year2xsyn` site artifacts.

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.

**A04-v2 transient:** no champion. Status is
`MODEL_DEVELOPMENT_INCOMPLETE_NO_CHAMPION` — long campaign still forbidden.
2026-08-18 final physics: Track B LIVE matrix **2,106 scored / 5,332 warmup** W2A
across **37** reports (superseded two-pass tree **3,780** scored kept on disk);
CLI instrumented Track B day **738 scored / 4,657 warmup**, active invalid-domain
**759**. Track C1/C2 one-W2A-per-zone children also failed scored-runtime W2A=0.
Terminal **B**: `RESEARCH_POC_ALLOWED` on A04 only; `SIMULATION_TRAINING_READY`
and `OPERATIONAL_DSM_READY` remain false. Audit:
[`docs/audits/2026-08-18-vibe22-final-physics-and-rl-poc.md`](docs/audits/2026-08-18-vibe22-final-physics-and-rl-poc.md).
Prior Track B readiness:
[`docs/audits/2026-08-18-vibe22-live-trackb-long-rl.md`](docs/audits/2026-08-18-vibe22-live-trackb-long-rl.md).
See [`docs/audits/2026-08-17-vibe22-trackb-physics-validity-v2.md`](docs/audits/2026-08-17-vibe22-trackb-physics-validity-v2.md)
(P0 accounting/continuity/DQN unique table / campaign factory; Track B still not a champion),
[`docs/audits/2026-08-17-vibe22-correctness-repair.md`](docs/audits/2026-08-17-vibe22-correctness-repair.md)
(reward v2 / Track B two-pass / A04 continuity),
[`docs/audits/2026-08-16-vibe22-a04v2-transient-nogo.md`](docs/audits/2026-08-16-vibe22-a04v2-transient-nogo.md)
(dated Stage A snapshot) and [`docs/audits/2026-08-17-vibe22-a04v2-model-development-continues.md`](docs/audits/2026-08-17-vibe22-a04v2-model-development-continues.md).

Read: [`vibe22_agent_spec/RL_DAILY_DSM.md`](vibe22_agent_spec/RL_DAILY_DSM.md) ·
[`vibe22_agent_spec/CONTRIBUTING_RL.md`](vibe22_agent_spec/CONTRIBUTING_RL.md) ·
[`skills/rl-daily-dsm/SKILL.md`](skills/rl-daily-dsm/SKILL.md)

```powershell
$env:SITE_ROOT="<SITE_ROOT>"
python scripts/a04_live_multiday_continuity.py --site-root $env:SITE_ROOT
python scripts/a04v2_trackb_two_pass.py --site-root $env:SITE_ROOT
python scripts/vibe22_instrumented_day.py --site-root $env:SITE_ROOT
python scripts/a04v2_trackc_one_w2a.py --variant c1 --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py operator-pay-experiment --mode smoke --reward-name operator_pay_2x_v1 --run-id oppay2x_smoke_20260816 --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py research-poc --confirm-simulation-only-physics-limits --max-wall-hours 6 --site-root $env:SITE_ROOT
python scripts/reproduce_physics_ramp_gate.py
```

`--mode full` must exit 4 until a **newly generated** ramp artifact has `passed=true`
*and* `contracts/active_rl_model_v1.json` has `long_campaign_allowed=true` with
verified hashes. `research-poc` is a **separate subcommand**, not an operator-pay
`--mode`. Missing `--confirm-simulation-only-physics-limits` exits 4. The research
contract cannot set `long_campaign_allowed=true`. EnergyPlus MCP (`user-energyplus`)
is for IDF/RDD inspection before edits; it cannot rewrite W2A banks. Track C stays
in Python. Control/action/observation v2: [`docs/audits/2026-08-17-vibe22-control-contract-v2.md`](docs/audits/2026-08-17-vibe22-control-contract-v2.md).
Track B archetype: [`docs/audits/2026-08-17-vibe22-trackb-model-development.md`](docs/audits/2026-08-17-vibe22-trackb-model-development.md) — preliminary capacity-class banks, not as-built, long RL still blocked.

Non-RL DSM/GL14/Streamlit: [`archive/2026-08-14_pre_rl_only/`](archive/2026-08-14_pre_rl_only/).
Do not restore `archive/2026-08-10_pre_eplus_gym`.
