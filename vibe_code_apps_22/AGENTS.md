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
and `OPERATIONAL_DSM_READY` remain false. `research-long` is a labeled overnight
research CLI (`RESEARCH_LONG_ALLOWED`) stacked on that PoC — still not a champion.
Audit:
[`docs/audits/2026-08-18-vibe22-final-physics-and-rl-poc.md`](docs/audits/2026-08-18-vibe22-final-physics-and-rl-poc.md).
Research-long launch:
[`docs/audits/2026-08-18-vibe22-research-long-launch.md`](docs/audits/2026-08-18-vibe22-research-long-launch.md).
Prior Track B readiness:
[`docs/audits/2026-08-18-vibe22-live-trackb-long-rl.md`](docs/audits/2026-08-18-vibe22-live-trackb-long-rl.md).
See [`docs/audits/2026-08-17-vibe22-trackb-physics-validity-v2.md`](docs/audits/2026-08-17-vibe22-trackb-physics-validity-v2.md)
(P0 accounting/continuity/DQN unique table / campaign factory; Track B still not a champion),
[`docs/audits/2026-08-17-vibe22-correctness-repair.md`](docs/audits/2026-08-17-vibe22-correctness-repair.md)
(reward v2 / Track B two-pass / A04 continuity),
[`docs/audits/2026-08-16-vibe22-a04v2-transient-nogo.md`](docs/audits/2026-08-16-vibe22-a04v2-transient-nogo.md)
(dated Stage A snapshot) and [`docs/audits/2026-08-17-vibe22-a04v2-model-development-continues.md`](docs/audits/2026-08-17-vibe22-a04v2-model-development-continues.md).

Read: [`vibe22_agent_spec/RL_DAILY_DSM.md`](vibe22_agent_spec/RL_DAILY_DSM.md) ·
[`vibe22_agent_spec/RESULTS_PUBLICATION.md`](vibe22_agent_spec/RESULTS_PUBLICATION.md) ·
[`vibe22_agent_spec/CONTRIBUTING_RL.md`](vibe22_agent_spec/CONTRIBUTING_RL.md) ·
[`skills/rl-daily-dsm/SKILL.md`](skills/rl-daily-dsm/SKILL.md) ·
[`skills/rl-poc-results-publish/SKILL.md`](skills/rl-poc-results-publish/SKILL.md) ·
[`skills/grid-search-comparator/SKILL.md`](skills/grid-search-comparator/SKILL.md) ·
[`skills/two-month-policy-replay/SKILL.md`](skills/two-month-policy-replay/SKILL.md) ·
[`skills/nightly-grid-compute/SKILL.md`](skills/nightly-grid-compute/SKILL.md) ·
[`skills/weather-trigger-replay/SKILL.md`](skills/weather-trigger-replay/SKILL.md)

**Finished research-long (2026-08-20):** PRIMARY `FLAT_PLUS_DEMAND` + SECONDARY
`ILLUSTRATIVE_TOU_PLUS_DEMAND` under `research_action_contract_v3`. Published pack:
[`docs/results/vibe22_rl_poc_results.md`](docs/results/vibe22_rl_poc_results.md).
Say **validation leader** (not winner); readiness only on checked school days;
disclose Dec billing floor; never invent E+ process launches; never mix flat/TOU `$`.
Regenerate with `python scripts/vibe22_publish_rl_poc_results.py --site-root $env:SITE_ROOT`.

**Grid comparator (2026-08-21):** LIVE fixed-policy discrete v3 exhaustive screen in
[`docs/results/grid_search/`](docs/results/grid_search/README.md). CLI:
`python scripts/vibe22_grid_search.py --site-root $env:SITE_ROOT …`. In **that**
Dec multi-day pack, daily adaptive branching is
`NOT_RUN_NO_IDENTICAL_STATE_BRANCHING_CONTRACT`.

**Two-month replay (2026-08-22):** [`docs/results/two_month_policy_replay/`](docs/results/two_month_policy_replay/) —
Dec 2025–Jan 2026 seven frozen strategies vs CS 351075. CLI:
`py -3.12 scripts/vibe22_two_month_policy_replay.py --site-root $env:SITE_ROOT --resume`.

**Nightly identical-state compute (2026-08-22):** [`docs/results/nightly_grid_compute/`](docs/results/nightly_grid_compute/) —
one-day lookback branching on `2026-01-26`; verdict
`NIGHTLY_GRID_FEASIBLE_WITHIN_15_MIN` (budget rec `25`). CLI:
`py -3.12 scripts/vibe22_nightly_grid_compute.py --site-root $env:SITE_ROOT --stage all --resume`.
Do not conflate with the Dec `grid_search/` pack.

**Weather-trigger continuous (2026-08-22):** [`docs/results/weather_trigger_continuous/`](docs/results/weather_trigger_continuous/) —
midnight-only cold-trigger vs continuous 68/74; verdict
`WEATHER_TRIGGER_IMPROVES_PEAK_WITH_ENERGY_PENALTY`. CLI:
`py -3.12 scripts/vibe22_weather_trigger_replay.py --site-root $env:SITE_ROOT --strategy all`.

```powershell
$env:SITE_ROOT="<SITE_ROOT>"
python scripts/a04_live_multiday_continuity.py --site-root $env:SITE_ROOT
python scripts/a04v2_trackb_two_pass.py --site-root $env:SITE_ROOT
python scripts/vibe22_instrumented_day.py --site-root $env:SITE_ROOT
python scripts/a04v2_trackc_one_w2a.py --variant c1 --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py operator-pay-experiment --mode smoke --reward-name operator_pay_2x_v1 --run-id oppay2x_smoke_20260816 --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py research-poc --confirm-simulation-only-physics-limits --max-wall-hours 6 --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py research-long --confirm-simulation-only-physics-limits --confirm-a04-not-transient-validated --micro-gate --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py research-long --confirm-simulation-only-physics-limits --confirm-a04-not-transient-validated --execute-live --max-wall-hours 30 --site-root $env:SITE_ROOT
python scripts/reproduce_physics_ramp_gate.py
```

`--mode full` must exit 4 until a **newly generated** ramp artifact has `passed=true`
*and* `contracts/active_rl_model_v1.json` has `long_campaign_allowed=true` with
verified hashes. `research-poc` is a **separate subcommand**, not an operator-pay
`--mode`. `research-long` is another separate subcommand (not an alias of
`campaign`). Missing either research-long confirm flag exits 4. The research
contract cannot set `long_campaign_allowed=true`. EnergyPlus MCP (`user-energyplus`)
is for IDF/RDD inspection before edits; it cannot rewrite W2A banks. Track C stays
in Python. Control/action/observation v2: [`docs/audits/2026-08-17-vibe22-control-contract-v2.md`](docs/audits/2026-08-17-vibe22-control-contract-v2.md).
Track B archetype: [`docs/audits/2026-08-17-vibe22-trackb-model-development.md`](docs/audits/2026-08-17-vibe22-trackb-model-development.md) — preliminary capacity-class banks, not as-built, long RL still blocked.

Non-RL DSM/GL14/Streamlit: [`archive/2026-08-14_pre_rl_only/`](archive/2026-08-14_pre_rl_only/).
Do not restore `archive/2026-08-10_pre_eplus_gym`.
