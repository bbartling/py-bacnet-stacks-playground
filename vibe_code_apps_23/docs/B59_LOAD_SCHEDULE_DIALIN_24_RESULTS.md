# Building 59 LOAD_SCHEDULE dial-in (24 runs)

**Claim status:** `LOAD_SCHEDULE_DIALIN_SCREENING_NOT_CALIBRATED`

Evidence-backed internal-load and schedule dial-in on the PackagedVAV screening
proxy (CONTROL_REPLAY R14 OA ×1.10 baseline). Axes: measured MEL/lighting
weekend–standby shapes, W/m² ladders toward measured annual end uses, HVAC
enable, occupancy hours, pandemic multipliers, fan pressure.

Topology (UFT / hydronic / water-cooled plant) is unchanged. A numeric monthly
GL14 pass on this proxy is **not** calibration or DSM readiness.

## Headline result

| Metric | Baseline R01 | Champion **R22** |
| --- | --- | --- |
| Full-year NMBE | −7.60% | **+3.05%** |
| Full-year CV(RMSE) | 23.79% | **13.23%** |
| Full-year GL14 numeric | fail | **pass** |
| Jan–Sep (tuning) | fail | fail (NMBE +6.89%) |
| Oct–Dec (reserved) | fail | fail (NMBE −14.7%) |

**R22 knobs:** MEL 5.5 W/m² + lights 3.5 W/m² + measured MEL standby/weekend
(0.40 / 0.65) + lights weekend 0.17 + continuous HVAC + supply fan **900 Pa**
(return 315 Pa). Softened fan rise is a sensitivity finding, not measured
fan-power evidence.

August remains the worst under-sim (~−27%). Nov/Dec over-sim shrinks vs prior
champions but is not fixed.

## What helped / hurt

- Raising MEL weekend/standby **without** cutting W/m² (R02) badly over-simulates.
- Cutting MEL W/m² toward measured annual kWh (R06) passes **tuning** GL14 but
  not full-year.
- Joint low loads + modest fan-pressure cut (R22) is the only full-year numeric
  passer in this menu.
- Weekday-only HVAC enable (R16) under-simulates the continuous-ish measured fans.

## Reproduce

```bash
cd vibe_code_apps_23
python scripts/run_b59_load_schedule_dialin_24.py \
  --energyplus /path/to/energyplus \
  --epw weather/b59_2020_bounded_hybrid_amy.epw \
  --workers 2
```

Artifacts: `scorecards/b59_2020_load_schedule_dialin_24/`,
`model/b59_load_schedule_dialin_champion.generated.idf`.

## Next

Still topology: UFT fans, hydronic reheat, water-cooled plant, end-use meters,
and measured SAT/OA/fan replay. Do not treat R22 as BAS/DSM authority.
