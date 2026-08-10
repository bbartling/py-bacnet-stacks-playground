# Grey-box forecast honesty (PR A)

**Date:** 2026-08-10  
**Honesty:** `GREYBOX_SHADOW_V1` / `NON_PROMOTABLE`  
**Blocking script:** `scripts/train_greybox_identification_v1.py` (nonzero exit on gate fail)

## Defect closed

`scripts/train_greybox_shadow_v1.py` previously scored holdout open-loop MAE using
`Q_eff` derived from **target-day** `facility_kw`. That input is unavailable in a
day-ahead / deployable advisor. The ~**0.48 °F** shadow holdout MAE is therefore
**`IDENTIFICATION_DIAGNOSTIC` only** — not a deployable 96-step forecast gate.

## Metric split

| Class | May use facility_kw → Q_eff? | Purpose |
|---|---|---|
| `IDENTIFICATION_DIAGNOSTIC` | Yes (exploratory ID / train) | Parameter exploration only |
| `DEPLOYABLE_FORECAST` | **No** — `Q_hvac=0` free-response | Honesty gate vs persistence |

Deployable API: `greybox.rc_1r1c.simulate_deployable` — rejects `facility_kw` and
`Q_eff_DIAGNOSTIC`.

## Physics gate (not MAE alone)

PASS requires all of:

1. Beats open-loop persistence on free-response / unoccupied days  
2. Parameters **not** bound-stuck (`a≈1` and `b≈floor` → `BOUND_HIT`)  
3. Plausible OAT response (`b` meaningfully above floor)

## Evidence (this run)

See `reports/ml/greybox_identification_scorecard.json`.

- Diagnostic holdout day MAE (meter Q): ~0.48 °F — **not deployable**
- Deployable free-response: can beat persistence on some days, but fit remains
  **`BOUND_HIT`** (`a≈1`, `b≈1e-6`) → physics FAIL
- Blocking script **exit code 1**
- Sensor manifest: plant actuators (HP stage, EWT/LWT, fan, …) still largely
  `UNKNOWN` / `NOT_IN_SITE_EXPORT`

## Verdict

```text
INSUFFICIENT_HVAC_INPUT_SENSOR_HUNT_REQUIRED
```

Do **not** clone to six zones. Do **not** promote. Keep IdealLoads hybrid as
`HYBRID_SCREENING` / W2A A04 as physical reference. Next: find real plant points
in FDD/Haystack exports before control-oriented Q.

## Hybrid runtime fail-closed

`ml/hybrid_rollout.py` no longer fills missing features with `0` or weather with
RH=50 / GHI=0. Required `oat_f` / `rh_pct` / `ghi` length-96 must be finite.
