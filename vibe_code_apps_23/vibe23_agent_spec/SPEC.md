# Vibe 23 Agentic AI App Build Specification — LBNL Building 59 Calibration + DSM

**Project:** Vibe Code App 23  
**Building:** LBNL Building 59 / Shyh Wang Hall, Berkeley, California  
**Dataset:** Dryad DOI `10.7941/D1N33Q`  
**Predecessors:** Vibe 19 (operational evidence), Vibe 20 (EnergyPlus calibration), Vibe 22 (DSM comparators/optimization)

## 1. Purpose
Build a public, reproducible existing-building EnergyPlus case study from Building 59 telemetry. The first product is a credible physics baseline; DSM optimization is downstream.

Another engineer should be able to clone the repo, download the same public dataset, reconstruct the same measured targets, run the same model and reproduce the scorecard.

## 2. Source-backed starting facts
- Building 59 is a four-floor Berkeley Lab building completed in 2015.
- Published description: ~10,400 m² conditioned space across four floors; lower level mechanical, second level NERSC computing, third/fourth office.
- Office areas use raised-floor plenums / UFAD.
- Four rooftop units serve the office levels.
- The cleaned dataset reports 27 CSV files and 337 points from more than 300 sensors/meters.
- Dataset coverage is described as two office floors at 2,325 m² each.

A later field-control publication describes the office HVAC study area as about 6,038 m² and documents RTU/UFT/heat-pump details. That is useful evidence but creates an area discrepancy that must be resolved against the dataset metadata and geometry before calibration.

## 3. Architecture
```text
Dryad DOI/API
  -> safe download + hashes
  -> immutable raw telemetry + metadata
  -> inventory / Brick + point binding / timezone contract
  -> strict Open-FDD package + reviewed operational evidence
  -> measured hourly/monthly targets + evidence ledger
  -> EnergyPlus seed + actual-year weather
  -> measured/sim alignment
  -> GL14 + peak + end-use + zone-temperature scorecard
  -> calibrated/validated baseline
  -> DSM experiment contracts
```

## 4. Phase gates
### Phase 0 — acquisition
Safe downloader, source hash, ignored raw workspace, deterministic acquisition manifest.

### Phase 1 — evidence mapping
Inventory CSVs and metadata; identify timestamps, units and source point names; bind whole-building electric, HVAC end uses, zone temperatures, RTU/UFT controls, airflow and occupancy without guesses. Exit: `DATA_MAPPED`.

### Phase 2 — model seed
Resolve calibration scope/area, create the office-floor geometry and preserve documented UFAD/RTU/UFT behavior. Unknown construction properties remain bounded assumptions. Use actual-year weather. EnergyPlus must run without severe errors. Exit: `MODEL_SEED`.

### Phase 3 — calibration
Tune in engineering order:
1. occupancy, equipment and lighting schedules/base load;
2. thermostat and HVAC operating schedules;
3. envelope/infiltration assumptions;
4. ventilation/supply-air behavior;
5. fan/coil/equipment efficiency and controls;
6. residual end-use mismatches.

Every iteration records changed parameters and hashes.

Default gates:
- monthly `|NMBE| <= 5%`, `CV(RMSE) <= 15%`;
- hourly `|NMBE| <= 10%`, `CV(RMSE) <= 30%`.

Also inspect peak kW/time, load shape, HVAC end uses, equipment runtime and occupied zone temperatures.

### Phase 4 — validation
Hold out a period when data quality permits. A failed holdout sends the model back to calibration; do not tune on the holdout and still call it validation.

### Phase 5 — tariff
Research archived rates for the selected period. Until Building 59 account/rate assignment is proven, tariff evidence remains `CANDIDATE` or `ILLUSTRATIVE`; only account/period-bound evidence may be `VERIFIED`.

### Phase 6 — DSM
Transparent grid search and weather-trigger strategies first, then demand-limit/reset strategies, then MPC/RL only if justified.

## 5. Calibration-year selection
Do not choose a year only for convenience. Review missingness and controls first. 2020 contains material occupancy/control-regime changes and is not the default first calibration year without explicit modeling. 2018/2019 should be compared for data completeness and stable operation before one is frozen.

## 6. Software posture
- Python 3.12 tooling.
- Pandas/Numpy for telemetry and metrics.
- EnergyPlus remains an external engine.
- Open-FDD and `airboxlab/rllib-energyplus` are external, pinned integration targets; the lightweight Vibe 23 contracts do not install their full stacks in CI.
- Large data stay local, not in git.
- CI does not download the full 263 MB package.

## 7. First PR acceptance
- Vibe 22 stale PRs consolidated/closed.
- Vibe 23 agent/spec structure exists.
- safe Dryad downloader + inventory + power aggregation + calibration metrics exist.
- shared repo-level skill directory exists without deleting historical app-local skills.
- tariff and calibration claims are explicitly guarded.
