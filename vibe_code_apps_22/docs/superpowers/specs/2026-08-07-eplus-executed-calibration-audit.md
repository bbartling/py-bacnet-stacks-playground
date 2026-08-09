# Executed EnergyPlus multi-resolution calibration audit (2026-08-07)

## Operational recommendation

**NO-GO** for operational DSM / optimizer recommendations.

## Immutable baseline (pre-change)

Frozen at `reports/eplus/baseline/immutable_baseline_v1.json` (site) and mirrored under `ml/artifacts/eplus_baseline/`.

| Product | n | NMBE% | CV(RMSE)% | RMSE kW | MAE kW | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| A Utility monthly | 10 | −0.08 | 11.44 | — | — | PARTIAL-PERIOD SCREEN (not full-year GL14) |
| B Interval→monthly | 11 | ~3.01 | ~11.49 | — | — | NOT utility bills |
| C Hourly | 8064 | ~2.79 | ~96.97 | ~63.9 | ~44.2 | Fail calibrated-sim hourly screen |
| D 15-min DSM | 32253 | — | ~114.7 | ~75.6 | ~46.8 | Diagnostic only |

Physics: IdealLoads + fixed-COP proxy. Filename `gshp` is naming only.

## Executed campaign evidence

Smoke (`smoke_exec_20260807`): 2/2 EnergyPlus trials succeeded; both fail hourly; best CVRMSE ≈ 93.6% (`equip_mult=0.7`).

Bounded campaign (`bounded_exec_20260807`): **8/8 EnergyPlus trials succeeded**, 0 failed sims, 12 non-executable knobs rejected (not counted as runs).

| | Hourly CV(RMSE)% | RMSE kW | Status |
| --- | ---: | ---: | --- |
| Before (staged) | 96.97 | 63.92 | fail |
| Best after (`infil_mult=0.8`) | 87.97 | 57.99 | fail |
| Hourly gate | ≤30 | — | not met |

All 8 succeeded trials fail the hourly screen. Structural verdict: IdealLoads + fixed-COP inadequate for hourly DSM under this executed bounded search — recommend (A) physical plant/HP model or (B) measured-data ML for absolute kW with E+ monthly/engineering only.

## Methodology notes

- Design-day duplicate stamps: keep last per E+ stamp before scoring.
- Shape mismatches: reject (no silent truncate).
- Chronological periods + locked final 30-day holdout recorded; holdout must not tune.
- `p=1` published with every score (calibrated-sim DOF convention; G14-2023 text not purchased).
