# Vibe22 scientific-correctness repair (2026-08-17)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.

**Public line:** MODEL DEVELOPMENT INCOMPLETE — LONG RL BLOCKED

A04 was not overwritten. `ENGINEERING_MARGIN` was not raised. No PPO/DQN campaign.
No BACnet commands. `contracts/active_rl_model_v1.json` stays fail-closed.

## Status

| Item | Result |
| --- | --- |
| Reward v2 | landed (`reward_contract_v2` / `eplus_gym/rl/reward_v2.py`) |
| Recovery / PPO deadband / DQN no-wrap / obs v3 | landed |
| W2A parser | `runtime = total − warmup − sizing`; 46152 − 39052 − 0 = **7100** |
| Track B builder | 20 ZoneHVAC + coils + fans; reference integrity **ok** |
| Track B LIVE two-pass | **executed**; pass2 W2A scored-runtime **3780**; **not** a champion |
| A04 3-day continuity | **3 LIVE processes**, `n_process_starts=1` each |
| Champion | **none** |
| `long_campaign_allowed` | **false** |

## Reward v2 (frozen)

Utility: `daily_cost = energy_cost + demand_increment` with
`energy_rate=0.12`, `demand_rate=15`, `dt_h=0.25`.
`mtd_peak_kw` is not the billing floor (`max(mtd, ratchet, contract)`).

Display paycheck is human-only (clipped). Train reward is **not** the paycheck.

- Feasible: `clip(savings / 100, -5, 5) − 0.05·occupied_DH − 0.02·move`, then clip `[-5, 5]`
- Readiness fail (steps **30 and 31**, **68–74°F**, all six zones, school days): `-20 − normalized_DH`
- Readiness fail is strictly worse than any feasible train reward
- Crash / NaN / missing baseline → `IntegrityFailure`, not a learnable `-1e6`

Do not reinterpret published `operator_pay_2x_v1` smoke artifacts.

## Recovery

`recovery_lead_minutes` **is** the linear ramp duration ending at DualSP start.
First-change steps for `start=28`: lead 0/60/120/180 → `[28, 24, 20, 16]`.
PPO `setback_depth < 0.25°F` selects `CONTINUOUS_CONDITIONING_THERMOSTATIC`.
DQN indices outside `[0, n)` raise (no wrap).

## W2A parser

Real EnergyPlus recurring block is total / warmup / sizing. Unparseable phases
fail closed. Stage B rescore found **0** committed `eplusout.err` files
([`figures/vibe22_repair/stageb_w2a_rescore.json`](figures/vibe22_repair/stageb_w2a_rescore.json)).
Threshold remains scored-runtime **0**. No model was promoted.

## Track B LIVE two-pass

Not as-built. Not 67 identical 3-ton units. Parent A04 heating coils report
**User-Specified** 149430 W in every zone; airflow is Design Size. Banks split
those live eio totals. EnergyPlus 26.1 eio names are uppercase.

| Pass | Role | rc | Notes |
| --- | --- | --- | --- |
| 1 | A04 sizing + 1-day weather | 0 | live eio totals |
| 2 | child banks, short weather | 0 | completed; 2 severe (weatherfile year); W2A runtime 3780 |

Compact: [`figures/vibe22_repair/trackb_two_pass/`](figures/vibe22_repair/trackb_two_pass/).
Fat trees stay on `SITE_ROOT`. Regenerable IDF is gitignored.

`track_b_live_energyplus_executed=true`. `track_b_completed=false`.
`track_b_failed_honestly=false` (builder ran; gates did not pass; not a terminal NO-GO).

## A04 3-day continuity (immutable A04)

Gallery stays on A04 until a Track B champion exists.
`EnergyPlusContinuityPlant`: one process per arm. `reset()` consumes the first
RunPeriodWeather timestep (typically 00:15), so lookback is `lookback_days*96 − 1`
further steps. FakeContinuityPlant is not physics evidence.

| Arm | Process starts | Scored-runtime W2A |
| --- | --- | --- |
| continuous_70 | 1 | 0 (pass) |
| observed_bas_incumbent | 1 | 35124 (fail) |
| deep_setback | 1 | 36360 (fail) |

Days 2026-01-12 … 2026-01-14. Readiness **ok** on all three scored school days.
Deep setback used **less kWh** than continuous-70 but **higher** demand increment
/ daily cost (screening only — not savings).

| Day | cont kWh | incumbent kWh | deep kWh | incumbent train r | deep train r |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2026-01-12 | 3025 | 2576 | 2367 | +0.53 | −1.61 |
| 2026-01-13 | 2539 | 2232 | 2087 | −0.74 | −3.51 |
| 2026-01-14 | 3360 | 3051 | 2914 | −0.37 | −3.20 |

Manifest + plot: [`figures/vibe22_repair/a04_multiday_continuity/`](figures/vibe22_repair/a04_multiday_continuity/).

## LIVE EnergyPlus process count (evidence package)

**5** processes: Track B pass1, Track B pass2, three continuity arms.
Diagnostic CLI/API runs during eio/CRLF/calendar debugging are not this package.

## LONG RL

**NO-GO.** Do not start 5–10 sequence pilots or 20–30 h PPO/DQN without a later
explicit human authorization **and** a Track B champion that passes ramp,
demand-window, load-profile, six-zone transient, scored-runtime W2A, and
partial-period monthly screens.

## Reproduce

```powershell
$env:PYTHONPATH = "vibe_code_apps_22"
$env:SITE_ROOT = "<site pack>"
python -m pytest tests -q
python scripts/a04v2_trackb_two_pass.py --site-root $env:SITE_ROOT
python scripts/a04_live_multiday_continuity.py --site-root $env:SITE_ROOT
python scripts/a04v2_write_selection_verdict.py
```
