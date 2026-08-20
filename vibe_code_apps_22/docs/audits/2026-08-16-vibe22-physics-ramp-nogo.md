# Physics-ramp gate NO-GO (2026-08-16)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.

**Verdict:** `NO_GO_LONG_RL_TRAINING_PHYSICS_RAMP_IMPLAUSIBLE`

Long PPO/DQN training was **not started**. The BAS-informed threshold was **not** raised. A04 was **not** retuned against this gate.

## Executive verdict

Newly generated LIVE EnergyPlus Jan 26 trajectories on pinned A04 reproduce the committed failure:

| Quantity | Value |
| --- | --- |
| Threshold | `p99.9(BAS) × 3` ≈ **2.651 °F / 15 min** |
| Incumbent max (after recovery-window fix) | **4.616 °F / 15 min** |
| Low unocc (68/58) max | **8.203 °F / 15 min** |
| High occ (72/68, ramp=0) max | **3.989 °F / 15 min** |
| Lookback→target splice | ≈ **10⁻⁶ °F** (not the cause) |
| `passed` | **false** |

A trained policy may still **not** be claimed. `operator-pay-experiment --mode full` remains refused.

## What was ruled out

- **Lookback/target discontinuity:** 192-row splice |ΔT| is numerically zero.
- **Fahrenheit/Celsius mix-up:** zone and DualSP values sit in 65–70 °F.
- **Duplicate/missing gym steps:** 96 scored / 192 total, six BAS zone columns, facility kW present, Severe=0.
- **EnergyPlus clock as the gate index:** `ep_hour`/`ep_minute` are not a unique 15-minute grid (duplicate 23:60, stray minutes). The gate uses **gym `local_step` × 15 min**. That is a reporting-alignment defect, not the 4.6 °F jump.
- **Threshold retune:** `ENGINEERING_MARGIN` remains 3.0.

## Recovery-ramp software defect (fixed, insufficient)

Default incumbent has `recovery_ramp_minutes=60` but `recovery_start_minutes_before_occupancy=0`. The recovery window was `start - lead`, so with `lead=0` the ramp interval was **empty** and DualSP stepped 65→70 at occupancy start. Zone air followed in one timestep (~4.9 °F).

The window is now `start - lead - ramp` (same change in `parametric_daily_controller.py`). Morning occupancy breaches **cleared**. Evening DualSP setback 70→65 at `occupancy_end_step` still moves all six zones **~4.55–4.62 °F in 15 minutes**, above 2.65.

That evening jump is **A04 air-node tracking of a 5 °F DualSP step**, not a timestamp bug. Matching BAS p99.9 (~0.88 °F/15 min) would require a new model version (mass/capacity/plant) plus GL14 and peak re-screens — not a silent IDF tweak to pass this gate.

## Interval evidence (incumbent, after ramp fix)

All remaining incumbent breaches are **2026-01-26 17:30** (`local_step` 69), OAT ≈ −17.7 °C, DualSP 65 °F, prior zone ≈ 70 °F.

Plots/CSV: [`figures/postfix/ramp_repro/`](figures/postfix/ramp_repro/) (`incumbent_intervals.png`, `.csv`; low/high arms).

## Operational recommendation

**NO-GO** for long RL training and BACnet. Screening smoke on three gate days remains allowed. Do not call January a pristine holdout.

## Reproduction

```powershell
$env:SITE_ROOT="<SITE_ROOT>"
cd vibe_code_apps_22
python scripts/reproduce_physics_ramp_gate.py
python -m pytest tests -q
```

Exit code 4 from the reproduce script means the gate is still failed.
