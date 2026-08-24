# Building 59 EnergyPlus model workspace

The bootstrap PR intentionally does **not** fabricate a finished IDF before the public metadata/point bindings are inspected.

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
