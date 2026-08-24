# Building 59 EnergyPlus model workspace

`b59_screening_champion.generated.idf` is the exact IDF from the completed
50-run screening release. It is runnable and hash-bound, but it is intentionally
labelled `OFFICE_SCREENING_SEED_UNCALIBRATED`. It failed monthly GL14-style
CV(RMSE), reserved validation, end-use, topology, and identifiability gates.

The older `b59_seed.idf.template` remains a non-runnable provenance template.

## Seed topology target
- calibration scope: third/fourth office levels covered by measured data;
- raised-floor plenums / UFAD;
- four RTU service groups;
- perimeter underfloor terminal heating behavior where supported by source metadata;
- explicit internal/perimeter zone grouping that can later expand to the documented thermal-zone map;
- actual-year Berkeley weather;
- source/assumption ledger for envelope, windows, schedules, ventilation, capacities and controls.

## Geometry gate
The source literature contains at least two office-area figures (dataset monitored area vs later field-study area). Do not freeze geometry until this discrepancy is reconciled.

## Calibration gate
A model run is only `MODEL_SEED`. `MONTHLY_CALIBRATED`, `HOURLY_CALIBRATED` or `VALIDATED_HOLDOUT` require measured-vs-sim scorecards and the corresponding gates.

The current champion must not be promoted. Its close annual subtotal hides
large compensating errors in MELs, lighting, and HVAC; see
`../docs/B59_50_RUN_SCREENING_RESULTS.md`. The next model revision must use
actual occupancy, HVAC runtime, setpoint, airflow, terminal, zone, and plant
evidence before another bounded calibration search.

The hash-bound historical IDF also retains one stale explanatory comment that
says 12,000 cfm; its actual object field and frozen parameter manifest use
13,500 cfm. Do not edit that release artifact in place. The generator comment
is corrected, and any replacement IDF must receive a new version and hash.
