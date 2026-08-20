# RL daily six-zone DSM (LIVE EnergyPlus)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY

Not operational MPC. Not verified savings. Not BACnet.

**Status:** `MODEL DEVELOPMENT INCOMPLETE — LONG RL BLOCKED`

**Long campaign:** forbidden until a Track B champion passes ramp, demand-window, load-profile, six-zone transient, scored-runtime W2A, and partial-period monthly screens. Snapshot: [`../docs/audits/2026-08-16-vibe22-a04v2-transient-nogo.md`](../docs/audits/2026-08-16-vibe22-a04v2-transient-nogo.md). Repair: [`../docs/audits/2026-08-17-vibe22-correctness-repair.md`](../docs/audits/2026-08-17-vibe22-correctness-repair.md). Physics-validity v2: [`../docs/audits/2026-08-17-vibe22-trackb-physics-validity-v2.md`](../docs/audits/2026-08-17-vibe22-trackb-physics-validity-v2.md).

## Locked MDP (v2)

| Item | Value |
| --- | --- |
| Episode | 3/5/7 weather days, **one EnergyPlus process** (`EnergyPlusContinuityPlant`) |
| Simulator | `LIVE_ENERGYPLUS` only; campaign refuses `FakeContinuityPlant` |
| Action | Daily DualSP plan → six 96-step heating schedules (`control_v2`) |
| Recovery | `recovery_lead_minutes` is the linear ramp duration ending at start_step |
| PPO research v2 | `research_action_contract_v2`: normalized `Box[-1,1]^9` affine-decoded to 68–72 / 60–occ / 0–180 / offsets. v1 physical Box is frozen. |
| DQN research v2 | Unique table `Discrete(38)`; no wrap; actions 0/1 = continuous 68/70 |
| Readiness | Steps **30 and 31**, band **68–74°F**, **all six zones**, school days only |
| Reward | `reward_contract_v2`: utility accounting + display paycheck + unbounded-by-paycheck train reward; occupied low/high DH split; within-day movement is the training term |
| Integrity | crash / NaN / missing baseline / wrong timestep → invalid/truncated, not `-1e6` |
| IDF | `lakeside_w2a_a04_dual_champion.idf` fail-closed until a Track B champion exists |
| Gym | Campaign factory: `MultiDayDailyEnv` + `EnergyPlusContinuityPlant`. `DailySixZoneGymEnv` is legacy diagnostic only. |
| Trainer | Stable-Baselines3 PPO + DQN (not Ray) — **do not start** a full campaign |
| Track B | Later LIVE matrix **executed** (first child **2,106 scored / 5,332 warmup** W2A; **37** reports). Superseded two-pass tree **3,780** scored kept. CLI instrumented day **738 / 4,657** plus active invalid-domain **759**. Not a champion. |

**Terminal paths:** **A** = every champion gate passes → update `active_rl_model_v1.json` and long RL. **B** (this campaign) = no champion; bounded A04 `research-poc` / `research-long` labeled `RESEARCH_POC_ALLOWED` / `RESEARCH_LONG_ALLOWED`. **C** = EnergyPlus/RL computation itself failed. Do not call implementation complete.

EnergyPlus MCP (`user-energyplus`) inspects IDF/RDD before edits. MCP cannot rewrite W2A banks. Track C (`scripts/a04v2_trackc_one_w2a.py`) stays in Python. Output names come from the generated RDD, never guessed.

Frozen reward constants: `energy_rate=0.12`, `demand_rate=15`, `cost_scale=100`, `λ_occ=0.05`, `λ_move=0.02`.

## CLI

```powershell
python scripts/a04_live_multiday_continuity.py --site-root $env:SITE_ROOT
python scripts/a04v2_trackb_two_pass.py --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py operator-pay-experiment --mode smoke --reward-name operator_pay_2x_v1 --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py research-poc --confirm-simulation-only-physics-limits --max-wall-hours 6 --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py research-long --confirm-simulation-only-physics-limits --confirm-a04-not-transient-validated --micro-gate --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py research-long --confirm-simulation-only-physics-limits --confirm-a04-not-transient-validated --execute-live --max-wall-hours 30 --site-root $env:SITE_ROOT
```

`campaign --n-days 100` remains prohibited. Default campaign `reward_name` is `reward_v2`.
`research-poc` is not an operator-pay `--mode`. `research-long` is not an alias of `campaign`.
Missing either research-long confirm → exit 4. PPO research-long uses
`research_action_contract_v2` (`Box[-1,1]^9`). The SB3 `.zip` is canonical; do not
write a v2/dim-19 `daily_policy.pkl`. The research contract cannot enable
`long_campaign_allowed`.
`scripts/vibe22_rl.py campaign` constructs `MultiDayDailyEnv` via `train_sb3.make_env`.
`legacy-daily-env --confirm-legacy-diagnostic` is the only path to `DailySixZoneGymEnv`.
A04 3-day continuity gallery (`scripts/a04_live_multiday_continuity.py`) is screening only:
one EnergyPlus process per arm; `reset()` consumes schedule index 0; remaining lookback
uses indices **1..95**. Dual `BillingState` MTD peaks are independent.

Operator-pay v1 smoke artifacts are **not** reinterpreted by reward_v2.

Skill: [`../skills/rl-daily-dsm/SKILL.md`](../skills/rl-daily-dsm/SKILL.md).
