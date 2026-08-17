# Track B capacity-class archetype (2026-08-17)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.

**Status:** `MODEL DEVELOPMENT INCOMPLETE — LONG RL BLOCKED`

Public label: **PRELIMINARY CAPACITY-CLASS ARCHETYPE CONSTRAINED BY THE 67-UNIT BAS INVENTORY**

This is **not** an as-built model. It is **not** 67 identical three-ton units. It is
**not** one giant coil per RL group. A04 was not overwritten.

## Plant representation

Six BAS/RL control groups. Each group is allocated **multiple** EquationFit
heating banks (small/medium/large or two-bank) from the 67-unit inventory
counts. Tonnage is **not** asserted. Group total capacity is Autosize; documented
low/base/high fractions split that total after sizing.

EquationFit curves are inherited from parent A04 and labeled unverified catalog
coefficients until manufacturer submittals exist.

Ground loop / DOAS remain unconfirmed. Do not present boiler/tower topology as
the confirmed geothermal system.

## Gates

No LIVE Track B EnergyPlus campaign was run in this PR. Champion gates are
`not_run`. Scored-runtime W2A low-airflow bound remains 0. The 2.651 °F/15 min
ramp threshold is an **internal plausibility screen**, not ASHRAE validation.
5-minute demand from 15-minute native output remains unavailable.

`contracts/active_rl_model_v1.json` still has `long_campaign_allowed=false`.

Optional 3-day multi-day smoke and 5–10 sequence pilot were **not** run because
gates did not pass.

## Track B state

- `track_b_planned`: true
- `track_b_executed`: true (builder + bank plan + tests)
- `track_b_completed`: false
- `track_b_failed_honestly`: false

## Tests

```powershell
python -m pytest tests/test_trackb_banks.py tests -q
```

No BACnet commands. No trained-policy winner. Long RL remains NO-GO.
