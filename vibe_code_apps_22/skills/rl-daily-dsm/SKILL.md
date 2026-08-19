---
name: rl-daily-dsm
description: >-
  LIVE EnergyPlus daily six-zone RL on Lakeside A04. rleplus Gym/runner backend.
  SB3 PPO/DQN. One step = one weather day; one EnergyPlus process per multi-day
  episode (EnergyPlusContinuityPlant). Reward contract v2. No Ray, no Amphitheater IDF.
  Long campaign forbidden until a physics champion exists. Without a champion,
  only the labeled A04 research-poc subcommand is allowed (cannot set
  long_campaign_allowed).
---

# RL daily DSM (A04 + rleplus)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.

**Do not** start a 20–30 hour PPO/DQN campaign while the model is not transient-validated.
A04-v2 produced **no champion** (`MODEL_DEVELOPMENT_INCOMPLETE_NO_CHAMPION`).
Long RL remains blocked.

Use `contracts/reward_contract_v2.json` and `eplus_gym/rl/reward_v2.py` for new
multi-day work. Do **not** reinterpret published `operator_pay_2x_v1` smoke artifacts.
Campaigns must set `live_energyplus=true` via `EnergyPlusContinuityPlant`;
`FakeContinuityPlant` is a bookkeeping test double only.

`recovery_lead_minutes` is the linear ramp duration ending at DualSP start
(60/120/180 must differ). PPO `setback_depth < 0.25°F` selects
`CONTINUOUS_CONDITIONING_THERMOSTATIC`. DQN indices do not wrap.

W2A quality gates on **scored-runtime** only: `runtime = total - warmup - sizing`.

Track B two-pass LIVE EnergyPlus **ran**. The superseded two-pass tree scored **3,780**.
The later LIVE matrix (37 reports) scored **2,106 / 5,332 warmup** on the first
child (`40fb33e8…`) — still not a champion. CLI instrumented day: **738 scored /
4,657 warmup** plus active invalid-domain **759** (`runtime_fraction > 0.01` and
actual/rated air `< 0.25`). A04 heating capacity in the eio is **User-Specified
149430 W/zone**; airflow is Design Size. EnergyPlus 26.1 eio names are uppercase.

Track C sequential (not a matrix): C1 one-W2A-per-zone freeze ~603 kW scored W2A
**822**; C2 hard-size 800 kW scored **2016**. C3 skipped (unverified A04 curves).
Do not promote a topology merely because warnings drop.

`research-poc` is a separate CLI. Default twin is A04 labeled
`A04_RESEARCH_POC_NOT_TRANSIENT_VALIDATED`. Missing confirm flag exits 4.
`research-long` is a **different** subcommand (not an alias of `campaign`).
It requires both `--confirm-simulation-only-physics-limits` and
`--confirm-a04-not-transient-validated`. PPO uses `research_action_contract_v2`
(`Box[-1,1]^9` affine-decoded). The SB3 `.zip` is canonical; do not write a
v2/dim-19 `daily_policy.pkl`. `long_campaign_allowed` stays false.
Future agents: inspect IDF/RDD with EnergyPlus MCP first; MCP cannot rewrite
W2A banks. Frozen ramp stays **2.651 °F / 15 min**.

`EnergyPlusContinuityPlant.reset()` consumes schedule index 0; remaining lookback
uses indices 1..95 (not a second copy of 0 that drops 95). A04 3-day continuity
gallery: `n_process_starts==1` per arm.

Future `vibe22_rl.py campaign` constructs `MultiDayDailyEnv`, not
`DailySixZoneGymEnv` (legacy diagnostic subcommand only). DQN v2 advertises
unique post-clamp schedules (74), not Discrete(110).

See `docs/audits/2026-08-18-vibe22-final-physics-and-rl-poc.md` and
`docs/audits/2026-08-18-vibe22-research-long-launch.md`.
A04 remains immutable. Do not raise `ENGINEERING_MARGIN`.

```powershell
python scripts/a04_live_multiday_continuity.py --site-root $env:SITE_ROOT
python scripts/a04v2_trackb_two_pass.py --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py operator-pay-experiment --mode smoke --reward-name operator_pay_2x_v1 --run-id oppay2x_smoke_20260816 --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py research-poc --confirm-simulation-only-physics-limits --max-wall-hours 6 --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py research-long --confirm-simulation-only-physics-limits --confirm-a04-not-transient-validated --micro-gate --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py research-long --confirm-simulation-only-physics-limits --confirm-a04-not-transient-validated --execute-live --max-wall-hours 30 --site-root $env:SITE_ROOT
```

Long `campaign --n-days 100` is prohibited.

[`../../vibe22_agent_spec/CONTRIBUTING_RL.md`](../../vibe22_agent_spec/CONTRIBUTING_RL.md)

## Mega v3 program (scientific record — 2026-08-19)

**Do not** treat scaffold JSON or unit tests as completed experiment phases. Phases
that require live EnergyPlus or training stay `pending` until real evidence exists.

| Phase | Status |
| --- | --- |
| 2 | `in_progress` — PR [#111](https://github.com/bbartling/py-bacnet-stacks-playground/pull/111) (`feat/vibe22-mega-phase2-w2a-diagnosis`): W2A **hypothesis** + MCP evidence |
| 3 | `scaffold_complete` — child ledger contracts only |
| 4–17 | `pending` — live E+ / training required |
| 18 | `partial` — spec index only |
| 19–20 | `pending` |

**Phase 2 (hypothesis-only, no model edits):**

```powershell
python scripts/vibe22_mega_phase2_w2a_diagnosis.py `
  --mcp-load docs/audits/figures/vibe22_mega_phase2/mcp_load_idf_model.json `
  --mcp-summary docs/audits/figures/vibe22_mega_phase2/mcp_get_model_summary.json `
  --mcp-hvac docs/audits/figures/vibe22_mega_phase2/mcp_discover_hvac_loops.json
```

Audit: `docs/audits/figures/vibe22_mega_phase2/phase2_w2a_diagnosis.json`.
Conclusion strength must remain `LEADING_ROOT_CAUSE_HYPOTHESIS` until a child model
confirms causality at scored runtime.

**Scaffold branch (`feat/vibe22-mega-scaffold-local`):**

- Contract examples only: `tests/fixtures/mega/EXAMPLE_NOT_EXPERIMENT_RESULT/` (`label: EXAMPLE_NOT_EXPERIMENT_RESULT`).
- Fail-closed status runner: `python scripts/vibe22_mega_run_phases.py` → `docs/audits/figures/vibe22_mega/mega_run_status.json`.
- Never commit synthetic metrics under `docs/audits/figures/vibe22_mega/phase3/` … `phase20/`.
- Child pilot: `python scripts/a04_child_hp67_scaled_v1.py` → `docs/audits/figures/a04_child_hp67_scaled_v1/`.
- hp67 v2 two-pass: `python scripts/a04_child_hp67_two_pass_v2.py` → `docs/audits/figures/a04_child_hp67_scaled_v2/`.
- 24/7 reference figure: `python scripts/vibe22_reference_247_experiment.py`.
- Three-day pilot gate: `python scripts/vibe22_three_day_pilot.py` (obs v4 + tariff in `MultiDayDailyEnv`).
- **Pilot passed 2026-08-19:** research-long authorized on A04 fallback (`Terminal B` labels).
- Launch-readiness audit: `docs/audits/2026-08-19-vibe22-launch-readiness-second-research-long.md`.
- Live campaign heartbeat: `$SITE_ROOT/reports/eplus_gym/rl/research_long_heartbeat.json`.
- hp67 v2 two-pass: champion **failed** — use A04 parent for RL until a future child passes full physics gates.

```powershell
python scripts/vibe22_rl.py research-long --confirm-simulation-only-physics-limits --confirm-a04-not-transient-validated --obs-schema v4 --tariff-mode flat_illustrative --execute-live --heartbeat $env:SITE_ROOT/reports/eplus_gym/rl/research_long_heartbeat.json --site-root $env:SITE_ROOT
```

Index: [`../../vibe22_agent_spec/MEGA_V3_PHASES.md`](../../vibe22_agent_spec/MEGA_V3_PHASES.md).
BACnet command authority = 0. Vibe19 untouched. Honor `NO_PRISTINE_LOCKED_TEST_AVAILABLE`.
