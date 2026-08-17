# Control contract v2 and multi-day daily Gym (2026-08-17)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.

**Status:** `MODEL DEVELOPMENT CONTINUES — LONG RL BLOCKED`

This PR versions the daily control, observation, and action contracts and adds
`MultiDayDailyEnv`. It does **not** train PPO/DQN, does not create a Track B
champion, and does not issue BAS commands.

## What changed

- School occupancy is a calendar constraint (`school_calendar_v2.json`). The
  agent cannot move doors-open / attendance / dismissal.
- Readiness checks are 07:30 and 07:45 (steps 30 and 31). `SCHOOL_START_STEP=32`
  (08:00) remains on v1 paths only, labeled as an approximation.
- Heating DualSP start/end and recovery live in a safe envelope around that
  calendar. `end_step=96` means end of day and does not wrap to 0.
- Occupied and unoccupied setpoints may be equal.
  `CONTINUOUS_CONDITIONING_THERMOSTATIC` emits the same setpoint for all 96
  intervals. Equipment stays available; compressors are not commanded on.
- PPO action contract v2 raises the unoccupied high bound to 72°F.
- DQN action contract v2 is Discrete(110): actions 0 and 1 are 68°F and 70°F
  continuous conditioning. Discrete(64) v1 is frozen and not reinterpreted.
- Observation contract v3 carries 24 hourly OAT values labeled
  `PERFECT_EPISODE_FORECAST` when taken from EPW truth, plus previous action,
  previous-day peak/kWh, billing floor, and continuous-conditioning state.
- `MultiDayDailyEnv` takes one action per day and does not reset the plant at
  midnight. Unit tests use `FakeContinuityPlant` (explicitly not EnergyPlus).
  LIVE EnergyPlus must keep one process for the episode; copying six zone
  temperatures into a new EnergyPlus process is forbidden.
- `contracts/active_rl_model_v1.json` is fail-closed (`long_campaign_allowed=false`).
- Observed BAS incumbent replay is 68/64 with a 07:00 DualSP start — not A04
  `SCH_HtgSP` and not Gym 70/65.

## 24/7 representation

Label: **CONTINUOUS_CONDITIONING_THERMOSTATIC**. Not “running the compressor 24/7.”

## Multi-day continuity

One `start_episode()` per reset. Each `step` simulates 24 hours on the same
plant object. Month-to-date billing floor carries forward.

## Track B / long RL

Track B is still **planned, not executed**. Long RL remains **NO-GO**.

## Tests

```powershell
python -m pytest tests/test_control_contract_v2.py tests/test_multiday_env.py tests -q
```

No BACnet writes. No trained-policy winner.
