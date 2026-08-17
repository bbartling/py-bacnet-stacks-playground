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
| PPO | `occupied`, `setback_depth` (deadband 0.25°F → continuous), start, end, lead, 6 offsets |
| DQN | Unique post-clamp schedules (`Discrete(74)` on 2026-01-12); declared grid is 110; indices outside `[0, n)` rejected (no wrap); actions 0/1 = continuous 68/70 |
| Readiness | Steps **30 and 31**, band **68–74°F**, **all six zones**, school days only |
| Reward | `reward_contract_v2`: utility accounting + display paycheck + unbounded-by-paycheck train reward; occupied low/high DH split; within-day movement is the training term |
| Integrity | crash / NaN / missing baseline / wrong timestep → invalid/truncated, not `-1e6` |
| IDF | `lakeside_w2a_a04_dual_champion.idf` fail-closed until a Track B champion exists |
| Gym | Campaign factory: `MultiDayDailyEnv` + `EnergyPlusContinuityPlant`. `DailySixZoneGymEnv` is legacy diagnostic only. |
| Trainer | Stable-Baselines3 PPO + DQN (not Ray) — **do not start** a full campaign |
| Track B | LIVE two-pass **executed previously** (W2A runtime 3780; 2 DATA PERIOD Severes); year-aware EPW + sizing-only child are **code**, not a new champion |

Frozen reward constants: `energy_rate=0.12`, `demand_rate=15`, `cost_scale=100`, `λ_occ=0.05`, `λ_move=0.02`.

## CLI

```powershell
python scripts/a04_live_multiday_continuity.py --site-root $env:SITE_ROOT
python scripts/a04v2_trackb_two_pass.py --site-root $env:SITE_ROOT
python scripts/vibe22_rl.py operator-pay-experiment --mode smoke --reward-name operator_pay_2x_v1 --site-root $env:SITE_ROOT
```

`campaign --n-days 100` remains prohibited. Default campaign `reward_name` is `reward_v2`.
`scripts/vibe22_rl.py campaign` constructs `MultiDayDailyEnv` via `train_sb3.make_env`.
`legacy-daily-env --confirm-legacy-diagnostic` is the only path to `DailySixZoneGymEnv`.
A04 3-day continuity gallery (`scripts/a04_live_multiday_continuity.py`) is screening only:
one EnergyPlus process per arm; `reset()` consumes schedule index 0; remaining lookback
uses indices **1..95**. Dual `BillingState` MTD peaks are independent.

Operator-pay v1 smoke artifacts are **not** reinterpreted by reward_v2.

Skill: [`../skills/rl-daily-dsm/SKILL.md`](../skills/rl-daily-dsm/SKILL.md).
