---
name: rl-daily-dsm
description: >-
  LIVE EnergyPlus daily six-zone RL on Lakeside A04. rleplus Gym/runner backend.
  SB3 PPO/DQN. One step = one weather day; one EnergyPlus process per multi-day
  episode (EnergyPlusContinuityPlant). Reward contract v2. No Ray, no Amphitheater
  IDF. Long campaign forbidden until a physics champion exists. Without a
  champion, only labeled A04 research-poc / research-long are allowed (cannot set
  long_campaign_allowed). Use when training, evaluating, launching research-long,
  interpreting campaign manifests, or deciding Terminal A/B/C readiness.
---

# RL daily DSM (A04 + rleplus)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.

**Do not** start a 20–30 hour PPO/DQN `campaign` while the model is not
transient-validated. A04-v2 produced **no champion**
(`MODEL_DEVELOPMENT_INCOMPLETE_NO_CHAMPION`). Long RL remains blocked.
hp67 child models also **failed** champion gates — keep RL on A04 parent with
Terminal B labels until a future child passes full physics gates.

## Hard boundaries (fail closed)

- Campaigns must set `live_energyplus=true` via `EnergyPlusContinuityPlant`.
  `FakeContinuityPlant` is a bookkeeping test double only.
- BACnet command authority = **0**. Never invent command writes.
- Vibe19 / public Streamlit is **out of scope** unless the human explicitly
  asks to touch it.
- Never raise `ENGINEERING_MARGIN` or soften W2A scored-runtime gates to pass.
- Never treat training mean reward as a validation leader.
- Never compare absolute `$` across `FLAT_PLUS_DEMAND` and
  `ILLUSTRATIVE_TOU_PLUS_DEMAND`.
- Never say “17/17 ready” for school readiness. Non-school days auto-pass the
  readiness gate and are **not** school readiness success.

## Action / observation / reward (current research stack)

Use `contracts/reward_contract_v2.json` and `eplus_gym/rl/reward_v2.py` for
multi-day work. Do **not** reinterpret published `operator_pay_2x_v1` smoke
artifacts.

| Piece | Locked value |
| --- | --- |
| Action contract for finished research-long | `research_action_contract_v3` (Box10 + DQN table; `post_occupancy_extension_minutes` 0–180) |
| School occupancy | Immutable calendar; extension must not invent holiday occupancy |
| Cooling | Approximately fixed (~74/85); `cooling_action_space=false` |
| Observation | `obs_schema` v4, dim **206** for finished campaigns |
| Readiness | Steps **30–31**, band **68–74°F**, **all six zones**, **checked school days only** |
| Recovery | `recovery_lead_minutes` is the linear ramp duration ending at DualSP start |
| PPO continuous | `setback_depth < 0.25°F` → `CONTINUOUS_CONDITIONING_THERMOSTATIC` |
| DQN | Unique post-clamp schedules; indices do not wrap |
| Policy artifact | SB3 `.zip` is canonical; do not write a v2/dim-19 `daily_policy.pkl` |

`recovery_lead_minutes` values 60/120/180 **must** differ in schedule proof.
Schedule proof is required on every step for action-contract v3.

## Baseline contract (do not retcon)

Finished research-long campaigns used **`observed_bas_incumbent_v2`**:

- Heating ≈ **68°F occupied / 64°F unoccupied**, scheduled DualSP transitions
- Cooling ≈ **74°F occupied / 85°F unoccupied**
- Not A04 native `SCH_HtgSP`; not Gym DualSP 70/65

Field note (unresolved): reported actual BAS may use continuous **68/74**.
That conflict was **not** resolved before the campaigns. Do **not** relabel
historical baselines or claim modeled deltas as verified savings vs actual BAS.

Contract: `contracts/observed_bas_incumbent_v2.json`.

## Physics / Track status (scientific record)

W2A quality gates on **scored-runtime** only:
`runtime = total - warmup - sizing`.

Track B two-pass LIVE EnergyPlus **ran**. Superseded two-pass tree scored
**3,780**. Later LIVE matrix (37 reports) scored **2,106 / 5,332 warmup** on
the first child — still not a champion. CLI instrumented day: **738 scored /
4,657 warmup** plus active invalid-domain **759**. A04 heating capacity in the
eio is **User-Specified 149430 W/zone**; airflow is Design Size. EnergyPlus
26.1 eio names are uppercase.

Track C sequential (not a matrix): C1 ~603 kW scored W2A **822**; C2 hard-size
800 kW scored **2016**. C3 skipped (unverified A04 curves). Do not promote a
topology merely because warnings drop.

Frozen ramp stays **2.651 °F / 15 min**. A04 remains immutable.

## Research CLI (Terminal B)

`research-poc` and `research-long` are **separate** subcommands (not aliases of
`campaign` / operator-pay `--mode`).

- Missing confirm flags → exit **4**
- Labels: `A04_RESEARCH_POC_NOT_TRANSIENT_VALIDATED`, `RESEARCH_LONG_ALLOWED`
- `SIMULATION_TRAINING_READY` and `OPERATIONAL_DSM_READY` stay **false**
- `long_campaign_allowed` stays **false** (research contract cannot set true)
- Future agents: inspect IDF/RDD with EnergyPlus MCP first; MCP cannot rewrite
  W2A banks

`EnergyPlusContinuityPlant.reset()` consumes schedule index 0; remaining
lookback uses indices **1..95**. A04 3-day continuity gallery:
`n_process_starts==1` per arm.

Future `vibe22_rl.py campaign` constructs `MultiDayDailyEnv`, not
`DailySixZoneGymEnv` (legacy diagnostic only).

## Finished research-long campaigns (2026-08-20)

Authoritative SITE_ROOT runs (read-only; never rewrite manifests):

| Experiment | Run root under `$SITE_ROOT/reports/eplus_gym/rl/` |
| --- | --- |
| PRIMARY `FLAT_PLUS_DEMAND` | `research_long_flat_plus_demand_20260820T132506Z` |
| SECONDARY `ILLUSTRATIVE_TOU_PLUS_DEMAND` | `research_long_illustrative_tou_plus_demand_20260820T210304Z` |

Scale (do not conflate counters):

- Train: **44** days (`2025-11-01`..`2025-12-14`)
- Validation: **17** days (`2025-12-15`..`2025-12-31`)
- Checked school days in validation: **5** (Dec 15–19); unchecked: **12**
- `target_transitions` **8192** × PPO/DQN seeds 0–1
- Eval: **11** arms × 17 days = **187** rows
- `actual_energyplus_process_launches`: **null** in manifests — publish “not
  recorded”; **do not invent**

Publication language:

- Say **validation leader** in markdown/figures/slides
- Keep raw eval field name `winner` only inside JSON provenance
- Leaders are readiness-constrained deterministic costs — **not** training
  mean reward

Headline outcomes (modeled; simulation-only):

- PRIMARY validation leader `trained_ppo_seed0` ≈ **+$5.26** vs incumbent,
  **higher peak** — did **not** reduce peak or total cost
- SECONDARY validation leader `trained_dqn_seed1` ≈ **−$63.23** illustrative;
  energy down, demand/peak up; TOU **not** verified utility pricing
- Incumbent checked-school readiness was **0/5** on PRIMARY (auto-pass
  non-school must not be spun as ready)

December billing floor: all Dec 15 rows had `opening_mtd_kw = 0.0`.
**Disclose, do not re-score** (no arm-specific Dec 1–14 facility series for
offline MTD repair without re-running EnergyPlus).

Published pack: `docs/results/` via
`scripts/vibe22_publish_rl_poc_results.py`. Exhaustive discrete DQN-table LIVE
screen is **`NOT_RUN`**. See skill `rl-poc-results-publish` and
[`../../vibe22_agent_spec/RESULTS_PUBLICATION.md`](../../vibe22_agent_spec/RESULTS_PUBLICATION.md).

## Commands

```powershell
python scripts/a04_live_multiday_continuity.py --site-root $env:SITE_ROOT
python scripts/a04v2_trackb_two_pass.py --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py operator-pay-experiment --mode smoke --reward-name operator_pay_2x_v1 --run-id oppay2x_smoke_20260816 --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py research-poc --confirm-simulation-only-physics-limits --max-wall-hours 6 --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py research-long --confirm-simulation-only-physics-limits --confirm-a04-not-transient-validated --micro-gate --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py research-long --confirm-simulation-only-physics-limits --confirm-a04-not-transient-validated --obs-schema v4 --tariff-mode FLAT_PLUS_DEMAND --action-contract research_action_contract_v3 --execute-live --heartbeat $env:SITE_ROOT/reports/eplus_gym/rl/research_long_flat_plus_demand_heartbeat.json --site-root $env:SITE_ROOT
python scripts/vibe22_publish_rl_poc_results.py --site-root $env:SITE_ROOT
```

Long `campaign --n-days 100` is prohibited.

## Mega v3 program notes

**Do not** treat scaffold JSON or unit tests as completed experiment phases.
Phases that require live EnergyPlus or training stay `pending` until real
evidence exists. hp67 v2 champion **failed**. Three-day pilot passed 2026-08-19
and authorized research-long on A04 fallback (Terminal B).

Audits:

- `docs/audits/2026-08-18-vibe22-final-physics-and-rl-poc.md`
- `docs/audits/2026-08-18-vibe22-research-long-launch.md`
- `docs/audits/2026-08-19-vibe22-launch-readiness-second-research-long.md`
- `docs/audits/2026-08-20-vibe22-action-space-tariff-experiments.md`
- `docs/results/vibe22_rl_poc_results.md` (finished PoC pack)

[`../../vibe22_agent_spec/CONTRIBUTING_RL.md`](../../vibe22_agent_spec/CONTRIBUTING_RL.md) ·
[`../../vibe22_agent_spec/MEGA_V3_PHASES.md`](../../vibe22_agent_spec/MEGA_V3_PHASES.md) ·
[`../../vibe22_agent_spec/RESULTS_PUBLICATION.md`](../../vibe22_agent_spec/RESULTS_PUBLICATION.md)

Honor `NO_PRISTINE_LOCKED_TEST_AVAILABLE`.
