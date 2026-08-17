# A04-v2 model development continues — long RL blocked (2026-08-17)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.

**Status:** `STAGE_A_NO_CHAMPION_MODEL_DEVELOPMENT_INCOMPLETE`

**Public line:** MODEL DEVELOPMENT CONTINUES — LONG RL BLOCKED

`long_campaign_allowed` remains **false**. A04 was not overwritten. `ENGINEERING_MARGIN=3.0` was not weakened. Stage A artifacts were not deleted. The 2026-08-16 terminal Pareto NO-GO is withdrawn as a scientific conclusion; it remains a dated Stage A snapshot at [`2026-08-16-vibe22-a04v2-transient-nogo.md`](2026-08-16-vibe22-a04v2-transient-nogo.md).

## Stack

- Branch: `feat/vibe22-a04v2-transient`
- Base: `a5f6e770` (PR #97 tip; includes #96). #96/#97 stay OPEN.
- PR: https://github.com/bbartling/py-bacnet-stacks-playground/pull/98
- A04 SHA-256 (CRLF pin): `212a2835eabb8b3a316150815a61bc996bf1fda4191df655dbf74f1126132683`
- A04 SHA-256 (LF-normalized): `080ab87797c78df0c8efb257a52bba97f550ee628ec4bd1333801b2e104b21eb`
- EPW SHA-256: `87d7d9bfca7de4ac5b905ec1a65defc7622a78dac9444fc55cdef618ddf91fb2`
- EnergyPlus: 26.1.0

## Why Stage A was not a terminal hard Pareto

CapMult 28 incumbent native 15-minute max is **316.46 kW** vs billed ±10% band **[256.34, 313.30] kW**. The same trajectory’s aligned 30-minute max is **~313.6 kW**. Utility bills do not document the demand interval. A 15-minute EnergyPlus max is therefore **not** an unqualified billed-demand gate.

Gym DualSP 70/65 with 06:00–07:00 recovery is also not A04’s baked `SCH_HtgSP` (46°F until 03:15 = 06:45 minus `optimum_start_h=3.5`, then 70°F). LIVE Jan 26 smoke (not holdout): native `SCH_HtgSP` replay peak **288.16 kW**; Gym incumbent **239.77 kW**; delta **−48.4 kW**. Candidate peaks use the Gym/BAS incumbent contract only.

BAS train_dev winter weekdays: occupied SP median **68°F**, unoccupied **64°F**, occupancy start **07:00**.

## Frozen contracts

- Peak: [`figures/a04v2/peak_contract.json`](figures/a04v2/peak_contract.json) — `hard_gate_on_15min_vs_billed=false`; legacy 250–290 is diagnostic only.
- Stage A windows: [`figures/a04v2/stageA_peak_windows.json`](figures/a04v2/stageA_peak_windows.json)
- Incumbent: [`figures/a04v2/incumbent_control_contract.json`](figures/a04v2/incumbent_control_contract.json)
- LIVE schedule compare: [`figures/a04v2/incumbent_schedule_compare/compare.json`](figures/a04v2/incumbent_schedule_compare/compare.json)
- Plant: [`figures/a04v2/w2a_plant_inventory.json`](figures/a04v2/w2a_plant_inventory.json) — nine `Coil:Heating:WaterToAirHeatPump:EquationFit` objects, **identical 149430 W**, airflow Autosize; 67-HP split vs agg 79 published. Child IDFs may autosize both or scale by HP-count × 3 ton × 400 cfm/ton.
- Quality: [`figures/a04v2/quality_gate.json`](figures/a04v2/quality_gate.json) — `max_w2a_low_airflow=0` (EnergyPlus “occurred N total times”).
- Transients (train_dev): [`figures/a04v2/phase3/bas_transient_stats.json`](figures/a04v2/phase3/bas_transient_stats.json) — evening mean |ΔT| ≈ 0.143 °F / 15 min. CapMult 28 is **not** promoted.
- Parameter bounds: [`figures/a04v2/phase3/parameter_manifest.json`](figures/a04v2/phase3/parameter_manifest.json)
- Verdict writer: `scripts/a04v2_write_selection_verdict.py` (computed, not hand-copied)

## Stage B

32 LIVE EnergyPlus packages (resume ledger; failed runs retained). Development days 2026-01-12, 2026-01-20, 2026-01-17, 2026-02-09, 2025-12-06 (train_dev; not pristine holdout). Jan 25/26 and Mar 16 remain gate/smoke.

| Gate | Result |
| --- | --- |
| Trials | 32 (13 ramp `passed=true`, 19 ramp failed, 0 EnergyPlus crash) |
| Ramp threshold | unchanged 2.651 °F / 15 min, `ENGINEERING_MARGIN=3.0` |
| Warning gate (`w2a_low_airflow` total times ≤ 0) | **0 passed** |
| Dual ramp+warning finalists | **0** |
| Champion | none |

Autosize heating + CapMult 12 passed the three-arm ramp on several days (weekday, weekend, mild). HP-scaled 3-ton/HP at CapMult 12 also passed ramp on those days but still printed ~12k–16k W2A low-airflow warnings. Autosize reduced some episodes to ~10²–10³ warnings, not zero. Leaving 149430 W in place (`a04_capacity`) did **not** pass ramp at CapMult 12 + InternalMass 2000. No weighted-average champion.

Because there is no warning-gate finalist, the expensive ten-period monthly GL14-style screen was **not** run. Track B is started as a plan only ([`figures/a04v2/trackB/plan.json`](figures/a04v2/trackB/plan.json)): separately versioned physical plant child (W2A performance, loop pumps/fans, loop temperature, OA/DOAS, ground loop or documented approximation). Track B has **not** failed honestly; status is not terminal `NO_GO_LONG_RL_TRAINING_TRANSIENT_MODEL_NOT_VALIDATED`.

## Reproduce

```powershell
$env:SITE_ROOT="<site pack with eplus/weather + ml/artifacts>"
python -m pytest tests -q
python scripts/a04v2_write_selection_verdict.py
python scripts/a04v2_stage_b_campaign.py
```

Long PPO/DQN remains refused until a **newly versioned** champion has a committed `ramp_gate.json` with `passed=true` for that model (postfix A04 artifact stays `passed=false`).
