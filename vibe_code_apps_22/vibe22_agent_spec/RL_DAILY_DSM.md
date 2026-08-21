# RL daily six-zone DSM (LIVE EnergyPlus)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY

Not operational MPC. Not verified savings. Not BACnet.

**Status:** `MODEL DEVELOPMENT INCOMPLETE — LONG RL BLOCKED`

**Long campaign:** forbidden until a Track B champion passes ramp, demand-window,
load-profile, six-zone transient, scored-runtime W2A, and partial-period monthly
screens. hp67 children also failed — keep Terminal B research on A04 parent.
Snapshot: [`../docs/audits/2026-08-16-vibe22-a04v2-transient-nogo.md`](../docs/audits/2026-08-16-vibe22-a04v2-transient-nogo.md).
Repair: [`../docs/audits/2026-08-17-vibe22-correctness-repair.md`](../docs/audits/2026-08-17-vibe22-correctness-repair.md).
Physics-validity v2: [`../docs/audits/2026-08-17-vibe22-trackb-physics-validity-v2.md`](../docs/audits/2026-08-17-vibe22-trackb-physics-validity-v2.md).

## Locked MDP (v2/v3 research)

| Item | Value |
| --- | --- |
| Episode | 3/5/7 weather days (smoke) or multi-day train/val windows; **one EnergyPlus process** (`EnergyPlusContinuityPlant`) per continuity episode |
| Simulator | `LIVE_ENERGYPLUS` only; campaign refuses `FakeContinuityPlant` |
| Action | Daily DualSP plan → six 96-step heating schedules (`control_v2`) |
| Finished research-long action contract | `research_action_contract_v3` (adds `post_occupancy_extension_minutes`; school occupancy immutable; schedule proof every step; cooling not actuated) |
| Recovery | `recovery_lead_minutes` is the linear ramp duration ending at start_step |
| PPO | Normalized Box affine-decoded; continuous when setback depth &lt; 0.25°F |
| DQN | Unique post-clamp table; no wrap; continuous 68/70 reachable |
| Readiness | Steps **30 and 31**, band **68–74°F**, **all six zones**, **checked school days only** |
| Reward | `reward_contract_v2`: utility accounting + display paycheck + unbounded-by-paycheck train reward |
| Integrity | crash / NaN / missing baseline / wrong timestep → invalid/truncated, not `-1e6` |
| IDF | `lakeside_w2a_a04_dual_champion.idf` fail-closed until a Track B champion exists |
| Baseline for finished campaigns | `observed_bas_incumbent_v2` (68/64 scheduled; do not retcon to continuous 68/74) |
| Observation (finished campaigns) | `obs_schema` v4, dim 206 |
| Gym | Campaign factory: `MultiDayDailyEnv` + `EnergyPlusContinuityPlant`. `DailySixZoneGymEnv` is legacy diagnostic only. |
| Trainer | Stable-Baselines3 PPO + DQN (not Ray) — **do not** start unlabeled `campaign --mode full` |
| Track B | Later LIVE matrix **executed** (first child **2,106 scored / 5,332 warmup** W2A; **37** reports). Not a champion. |

**Terminal paths:** **A** = every champion gate passes → update `active_rl_model_v1.json` and long RL. **B** (current) = no champion; labeled A04 `research-poc` / `research-long`. **C** = EnergyPlus/RL computation itself failed. Do not call implementation complete.

EnergyPlus MCP (`user-energyplus`) inspects IDF/RDD before edits. MCP cannot rewrite W2A banks. Output names come from the generated RDD, never guessed.

Frozen reward constants: `energy_rate=0.12`, `demand_rate=15`, `cost_scale=100`, `λ_occ=0.05`, `λ_move=0.02`.

## Finished dual-tariff research-long (2026-08-20)

| Experiment | Tariff | Validation leader | Modeled note |
| --- | --- | --- | --- |
| PRIMARY | `FLAT_PLUS_DEMAND` | `trained_ppo_seed0` | ≈ +$5.26 vs incumbent; higher peak; did not reduce cost/peak |
| SECONDARY | `ILLUSTRATIVE_TOU_PLUS_DEMAND` | `trained_dqn_seed1` | ≈ −$63.23 illustrative; energy down, demand/peak up |

Run roots:

- `.../research_long_flat_plus_demand_20260820T132506Z`
- `.../research_long_illustrative_tou_plus_demand_20260820T210304Z`

Publication rules (readiness wording, Dec billing floor, counters, honesty
labels): [`RESULTS_PUBLICATION.md`](RESULTS_PUBLICATION.md).

## CLI

```powershell
python scripts/a04_live_multiday_continuity.py --site-root $env:SITE_ROOT
python scripts/a04v2_trackb_two_pass.py --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py operator-pay-experiment --mode smoke --reward-name operator_pay_2x_v1 --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py research-poc --confirm-simulation-only-physics-limits --max-wall-hours 6 --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py research-long --confirm-simulation-only-physics-limits --confirm-a04-not-transient-validated --obs-schema v4 --tariff-mode FLAT_PLUS_DEMAND --action-contract research_action_contract_v3 --execute-live --site-root $env:SITE_ROOT
python scripts/vibe22_publish_rl_poc_results.py --site-root $env:SITE_ROOT
```

`campaign --n-days 100` remains prohibited. Default campaign `reward_name` is `reward_v2`.
`research-poc` is not an operator-pay `--mode`. `research-long` is not an alias of `campaign`.
Missing either research-long confirm → exit 4. The SB3 `.zip` is canonical; do not
write a v2/dim-19 `daily_policy.pkl`. The research contract cannot enable
`long_campaign_allowed`.
`scripts/vibe22_rl.py campaign` constructs `MultiDayDailyEnv` via `train_sb3.make_env`.
`legacy-daily-env --confirm-legacy-diagnostic` is the only path to `DailySixZoneGymEnv`.
A04 3-day continuity gallery: one EnergyPlus process per arm; `reset()` consumes
schedule index 0; remaining lookback uses indices **1..95**. Dual `BillingState`
MTD peaks are independent — and finished validation windows opened December MTD
at **0 kW** (disclose; see RESULTS_PUBLICATION).

Operator-pay v1 smoke artifacts are **not** reinterpreted by reward_v2.

Skills: [`../skills/rl-daily-dsm/SKILL.md`](../skills/rl-daily-dsm/SKILL.md) ·
[`../skills/rl-poc-results-publish/SKILL.md`](../skills/rl-poc-results-publish/SKILL.md).
