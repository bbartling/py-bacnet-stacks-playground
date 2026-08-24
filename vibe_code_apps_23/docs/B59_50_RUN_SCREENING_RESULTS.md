# Building 59 50-run EnergyPlus screening results

**Executed:** 2026-08-24  
**EnergyPlus:** 26.1.0-6f2e40d102  
**Status:** `CALIBRATION_IN_PROGRESS_BEST_EFFORT`  
**Decision:** monthly GL14-style numeric gate **not met**; model is **not calibrated or DSM-ready**

## Outcome

The released campaign executed exactly 50 deterministic candidate slots. All
50 returned code zero, produced 8,784 unique hourly records, and had zero
warning, severe, or fatal markers in the scanned logs. Historical R49 had an
incomplete ancillary EIO, disclosed below; a post-release repeat passed the
strengthened complete-EIO admission gate. R47–R50 are byte-for-byte repeatable
at the requested hourly CSV:

- IDF SHA-256: `7096c0ae7a749b800458b420d8936ed2e6146252178c998e9ba6f01b549fffa6`
- EPW SHA-256: `8ab9ce9094a76a5c70ffaf0136388137ddeb0ba7caa20e824d09888daa3197de`
- output CSV SHA-256: `f9b1f213a2a237e33abefeb93353ec726f27daa05634bfbdc10b2dcc8776b6c6`

Independent review found R49's ancillary `eplusout.eio` sizing report truncated
despite its complete/identical hourly output. The admission gate now also
requires the EIO `End of Data` terminator. A serial post-release champion run
passed that strengthened gate and reproduced the same hourly CSV byte-for-byte;
see `postrelease_champion_validation.json`. The historical R49 anomaly remains
disclosed and its sizing file is not used as evidence.

The selection objective used January–September. October–December was not used
by the selection code, but its metrics were computed and stored for every run;
the slice was therefore **not blind** and is not called a holdout.

| Evaluation slice | n | Diagnostic p | NMBE | CV(RMSE) | Monthly numeric gate |
| --- | ---: | ---: | ---: | ---: | --- |
| Jan–Sep selection | 9 | 1 | +1.33% | 17.86% | Fail — CV(RMSE) > 15% |
| Oct–Dec reserved validation | 3 | 1 | −33.88% | 43.63% | Fail |
| Full 2020 | 12 | 1 | −4.13% | 22.36% | Fail — CV(RMSE) > 15% |

`p=1` is retained only for continuity with the repository diagnostic. It is
not a defensible degrees-of-freedom count for a multi-family search and cannot
support a Guideline 14 calibration claim.

## Why the close annual bias is misleading

The champion's annual partial proxy is only 3.78% above the derived measured
subtotal, but it reaches that total through large offsetting end-use errors.

| Category | Measured | Simulated | Simulated − measured | Disposition |
| --- | ---: | ---: | ---: | --- |
| MELs | 28,548 kWh | 89,576 kWh | +213.78% | Provisional category mapping |
| South lighting | 6,421 kWh | 34,789 kWh | +441.82% | North lighting is absent from telemetry |
| HVAC panels vs mapped RTU fans/cooling | 307,951 kWh | 231,529 kWh | −24.82% | Measured panels include unresolved elevator/plant loads |
| Derived subtotal vs partial proxy | 342,919 kWh | 355,895 kWh | +3.78% | Aggregate screening comparison only |
| Unmetered north-lighting heat gain | — | 34,789 kWh | — | Excluded from target proxy |
| Electric terminal-reheat proxy | — | 626,220 kWh | — | Excluded; not the documented hydronic UFT plant |
| Facility total | — | 1,016,903 kWh | — | Forbidden comparison against office subtotal |

This is compensating error, not calibration. The champion also piles up on
aggressive hypotheses: continuous HVAC availability, 11 W/m² lighting,
15 W/m² equipment, 23.2°C cooling setpoint, 142.4 kW/RTU cooling, COP 4.1,
and the 13,500 cfm proxy-coil airflow upper bound.

## Evidence boundary

The public 2020 electrical target has 35,136 complete 15-minute samples and is
defined exactly as `mels_S + mels_N + lig_S + hvac_S + hvac_N`. It is a derived
office subtotal, not a utility bill or whole-building meter. Its timestamps are
treated as UTC under a documented analyst hypothesis; the publisher did not
embed timezone metadata.

The weather input has 8,784 fixed-PST hours. Campus weather supplies 8,776
hours of dry bulb, dew point, relative humidity, and GHI; the final eight hours
and auxiliary EPW fields use explicitly hashed Open-Meteo inputs. It is a
bounded hybrid actual-year weather file, not a pure measured AMY.

The seed represents two 2,325 m² office floors, four RTU service groups, 24
aggregate occupied zones, and 24 UFAD plenum proxies. It does not yet reproduce
the documented 57-zone/50-UFT mapping, water-cooled DX/tower loop, hydronic UFT
heat-pump plant, common fan-speed controller, elevators, or other floors.

## Pre-release QA disclosure

Engineering smoke tests and two aborted harness pilots preceded the released
50-row ledger. They exposed and fixed three orchestration defects: concurrent
preprocessors sharing a fixed-name symlink, interpolated schedules not aligned
to the 15-minute timestep, and incomplete ReadVars output not being rejected.
Those attempts are not counted as extra calibration candidates and were not
used to widen bounds, but their existence means this work must not be described
as a pristine blind preregistration. The final 50-run ledger is the reproducible
screening release.

## Next evidence-driven iteration

Do not run another material/construction search yet. The next campaign should:

1. Resolve the electrical boundary: elevator contribution, ASHP/WSHP and tower
   electricity, missing north lighting, and any shared/common loads.
2. Freeze per-stream timestamp, DST, interval-end, and local-standard-time
   transforms; rebuild monthly and demand targets on the same basis as E+.
3. Reconcile the 4,650 m² and approximately 6,038 m² office-scope evidence and
   map the documented 57 zones, 50 UFTs, four RTUs, and plant topology.
4. Use Open-FDD as a read-only evidence check for schedules, fan enable,
   economizer/OA/SAT behavior, UFT operation, and sensor exclusions.
5. Add hourly end-use, peak, zone-temperature, control, and transient gates.
6. Predeclare a genuinely inaccessible holdout and a defensible GL14 `p` before
   any candidate runs; do not compute or expose holdout metrics while tuning.
7. Run local sensitivity/identifiability and synthetic parameter-recovery tests
   before treating fitted values as physical.

Grid-flexibility and `airboxlab/rllib-energyplus` experiments remain blocked
until hourly/physics/transient gates pass. Tariff dollars remain scenario-only
until an account- and period-specific Building 59 rate is verified.

## Published artifacts

- `scorecards/b59_2020_screening/campaign_summary.json`
- `scorecards/b59_2020_screening/campaign_log.csv`
- `scorecards/b59_2020_screening/campaign_results.jsonl`
- `scorecards/b59_2020_screening/champion_monthly_comparison.csv`
- `scorecards/b59_2020_screening/champion_end_use_scope_audit.csv`
- `scorecards/b59_2020_screening/figures/`
- `model/b59_screening_champion.generated.idf`
- `weather/b59_2020_epw_manifest.json`

> **CALIBRATION_IN_PROGRESS_BEST_EFFORT — NOT A CALIBRATED OR DSM-READY MODEL.**
> This bounded 50-run EnergyPlus campaign did not pass monthly, hourly, peak,
> end-use, zone, control, transient, provenance, or independent-validation gates. The
> reported candidate is the lowest-ranked physically runnable selection-period
> run under the implemented objective, not proof that its parameters are
> uniquely identified or that it predicts savings. Derived electrical totals
> are not utility bills. No result authorizes tariff settlement, DSM savings
> claims, BACnet commands, or operational deployment.
