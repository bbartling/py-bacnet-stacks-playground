# ML Architecture — Vibe 21

## 1. Purpose

Vibe 21 converts Vibe 19 operational evidence and Vibe 20 EnergyPlus physics into deployable, auditable machine-learning twins.

The design deliberately separates:

1. **operational time-series models** — timestep-level inference from BAS/weather/history;
2. **scenario surrogate models** — scenario-level approximation of EnergyPlus outcomes;
3. **FDD classifiers** — optional fault labels/probabilities;
4. **virtual sensor regressors** — optional estimates of unmeasured engineering quantities.

These model families may share a feature compiler and model registry, but they do not share targets blindly.

---

## 2. Why not one giant multi-output model?

A multi-output regressor is technically possible, but the first production version should prefer separate target models because:

- instantaneous kW, interval kWh, annual kWh, gas use, unmet hours, and fault labels exist at different time scales;
- their errors have different engineering meaning;
- different targets may need different feature sets;
- separate models are easier to validate, replace, explain, and deploy;
- a single bad target should not force replacement of every other model;
- target leakage is easier to detect when each model has one explicit objective.

A multi-output experiment is acceptable when targets are truly co-indexed and the experiment demonstrably improves performance or consistency.

scikit-learn supports both native multi-output estimators (for example RandomForestRegressor) and the `MultiOutputRegressor` meta-estimator, which fits one regressor per target.

---

## 3. Canonical input families

### 3.1 Weather/exogenous features

Examples:

- outdoor dry-bulb temperature;
- outdoor relative humidity;
- dew point / wet bulb when defensibly available;
- solar radiation;
- wind speed when useful;
- hour of day;
- day of week;
- month / season;
- holiday flag;
- occupied flag;
- cooling/heating degree proxies.

### 3.2 BAS state features

Examples:

- zone temperature and setpoint;
- supply-air temperature and setpoint;
- duct static and setpoint;
- VAV airflow and airflow setpoint;
- damper position;
- heating/cooling valve position;
- fan status/speed/power;
- chiller status/power;
- pump status/power;
- plant temperatures;
- whole-building meter power when available.

### 3.3 Engineering-derived features

Examples:

- `zone_temp_error`;
- `sat_error`;
- `oat_zone_delta`;
- `oat_sat_delta`;
- `fan_kw_per_cfm`;
- `cooling_kw_per_ton` when both terms are valid;
- damper saturation flag;
- simultaneous heating/cooling proxy;
- economizer opportunity;
- after-hours runtime;
- occupied runtime;
- control error bands.

### 3.4 Historical/time-window features

Examples:

- previous 5/15/30/60-minute demand;
- previous zone/SAT values;
- rolling mean/std/min/max over trailing windows;
- trailing slope / rate of change;
- trailing runtime fraction;
- trailing comfort-error fraction.

All windows are **backward-looking only**.

### 3.5 Scenario features for the surrogate model

Examples:

- climate/weather identifier or weather-summary features;
- equipment capacity multipliers;
- fan/pump sizing multipliers;
- COP/efficiency parameters;
- schedule start/stop times;
- occupancy/load multipliers;
- thermostat setpoints;
- SAT/duct-static/reset strategy parameters;
- ventilation fraction;
- economizer enable/disable;
- infiltration multiplier;
- envelope/glazing parameters;
- control strategy ID;
- fault type/severity;
- calibrated-parameter uncertainty sample ID.

---

## 4. Canonical target design

### 4.1 Operational electric demand

Primary target:

```text
building_kw_avg_interval
```

Optional forecast targets use separate horizon-specific models:

```text
building_kw_t_plus_15m
building_kw_t_plus_60m
```

### 4.2 Electrical energy

For a regular interval whose target is average kW over that interval:

```text
interval_kwh = predicted_kw_avg_interval * interval_hours
```

Examples:

- 5 min: `kWh = kW × 5/60`;
- 15 min: `kWh = kW × 0.25`;
- 60 min: `kWh = kW × 1.0`.

This derived-energy approach is preferred because it enforces physical consistency.

Daily/monthly/annual energy may then be aggregated from predicted intervals **if the operational model covers the complete period**.

A separate daily/monthly/annual energy model is permitted when the product needs coarse-horizon prediction from coarse inputs, but it receives its own model ID and validation.

### 4.3 Gas/thermal energy

Possible targets:

```text
natural_gas_therm_interval
natural_gas_therm_month
heating_energy_kwh_equiv
```

Do not infer gas from electric kW unless the model explicitly represents that relationship and is validated against gas targets.

### 4.4 Scenario surrogate outputs

Scenario-level targets may include:

```text
annual_electricity_kwh
annual_natural_gas_therm
peak_electric_demand_kw
unmet_hours
comfort_violation_hours
cooling_end_use_kwh
heating_end_use_kwh
fan_end_use_kwh
pump_end_use_kwh
```

Monthly energy can be represented either as 12 explicit targets or a long-form scenario-month dataset. The latter is preferred if month/weather descriptors are included because it avoids a brittle 12-column output contract.

---

## 5. Recommended first algorithms

### 5.1 Baselines

Always train:

- persistence / previous-value baseline for time-series demand when applicable;
- mean/seasonal baseline;
- Ridge regression.

### 5.2 Candidate nonlinear regressors

Operational demand:

- `HistGradientBoostingRegressor`;
- `RandomForestRegressor`;
- `ExtraTreesRegressor`.

Scenario surrogate:

- `HistGradientBoostingRegressor`;
- `RandomForestRegressor`;
- `ExtraTreesRegressor`.

The champion is selected from held-out metrics plus engineering sanity checks, not training score.

### 5.3 Multi-output option

A research/benchmark branch may compare:

```python
RandomForestRegressor()  # native multi-output
```

against:

```python
MultiOutputRegressor(HistGradientBoostingRegressor())
```

for co-indexed targets such as:

```text
[annual_electricity_kwh, peak_electric_demand_kw, annual_gas_therm]
```

The result must still report metrics per target.

---

## 6. Two-model architecture for demand + energy

### Model A — operational demand twin

**Inputs**

```text
current weather
current BAS state
trailing BAS/weather history
calendar/occupancy
static building metadata
```

**Output**

```text
predicted average electric demand, kW
```

**Derived**

```text
interval kWh
cumulative day kWh
cumulative selected-period kWh
```

### Model B — scenario surrogate

**Inputs**

```text
EnergyPlus scenario parameters
weather descriptors
schedule/control parameters
fault parameters
static calibrated model metadata
```

**Outputs**

```text
annual/monthly kWh
peak kW
annual gas
comfort/unmet-hour metrics
```

This distinction lets the live digital twin answer both:

- “What is this building likely drawing right now?”
- “What would this whole scenario do over a year?”

without running EnergyPlus online.

---

## 7. Feature compiler contract

A single versioned library function/package must generate the exact same feature semantics during training and inference.

Inputs:

- ordered timestamped rows;
- canonical role mapping;
- unit metadata;
- feature schema version;
- optional static/scenario metadata.

Outputs:

- feature matrix;
- feature quality/coverage report;
- warnings;
- provenance.

The compiler must reject or flag:

- missing required history;
- unit mismatch;
- duplicate/non-monotonic timestamps;
- future-looking windows;
- unsupported grid size;
- columns outside expected ranges when validation rules exist.

---

## 8. Dataset row contract

Every synthetic operational row should carry enough provenance to prevent leakage and support auditing:

```text
simulation_id
scenario_id
building_id
model_id
weather_id
seed
parameter_sample_id
fault_type
fault_severity
control_strategy
source = ENERGYPLUS_SIMULATED
timestamp
feature_schema_version
target_schema_version
```

Real BAS rows use:

```text
source = BAS_MEASURED | BAS_DERIVED
```

Do not silently merge these classes.

---

## 9. Synthetic simulation farm

The simulation farm should sample realistic parameter ranges rather than arbitrary noise.

Families:

- weather years/extremes;
- occupancy schedules/density;
- setpoints;
- ventilation/economizer behavior;
- fan and pump settings;
- HVAC capacity/efficiency;
- envelope/infiltration uncertainty;
- control sequences;
- operating faults;
- calibrated-parameter uncertainty.

Use bounded sampling such as Latin hypercube, Sobol/quasi-random, or carefully stratified/random sampling when available. Preserve the exact sampled parameters in the scenario manifest.

Do not generate 100,000 near-identical simulations merely to claim scale.

---

## 10. Split and validation strategy

### 10.1 Synthetic holdout

Split by complete `simulation_id` / scenario groups.

A row from one simulation must never appear in both train and test simply because it has a different timestamp.

### 10.2 Temporal holdout

For real BAS data, hold out contiguous future periods rather than random rows.

Examples:

- train: January–April;
- validation: May;
- test: June–July;

or use rolling/blocked time-series validation.

### 10.3 Domain holdout

Reserve meaningful extremes when practical:

- hottest/coldest weather subset;
- selected fault severities;
- selected schedule regimes;
- selected capacity regimes.

This tests extrapolation honestly.

### 10.4 Real-building transfer check

After synthetic training, compare against real BAS/meter periods not used for calibration when available.

Report synthetic and real-domain metrics separately.

---

## 11. Metrics

Demand regression:

- MAE kW;
- RMSE kW;
- normalized RMSE where appropriate;
- R²;
- peak error kW and %;
- bias;
- time-of-peak error when relevant.

Energy regression/aggregation:

- MAE/RMSE kWh;
- CVRMSE;
- NMBE where appropriate;
- monthly/annual bias;
- cumulative energy error.

Fault classification:

- precision;
- recall;
- F1;
- confusion matrix;
- per-class support;
- probability calibration when probabilities are exposed.

Always report target units.

---

## 12. Prediction uncertainty and domain warnings

The first release does not need a sophisticated Bayesian model, but it must expose whether the request is inside the training envelope.

Possible first-release checks:

- per-feature min/max or robust percentile envelope;
- categorical membership;
- missing-feature count;
- distance/novelty score if implemented;
- ensemble spread for compatible estimators;
- explicit `OUT_OF_TRAINING_DOMAIN` warning.

Do not present a confidence percentage that has no statistical definition.

---

## 13. Model bundle

Suggested structure:

```text
models/<building_or_model_family>/
├── demand_now.joblib
├── demand_15m.joblib
├── demand_60m.joblib
├── scenario_energy.joblib
├── scenario_peak_kw.joblib
├── scenario_gas.joblib
├── model_registry.json
├── feature_schema.json
├── target_schema.json
├── training_manifest.json
├── validation_report.json
└── checksums.sha256
```

Only files declared in the registry and matching expected SHA-256 hashes may be loaded.

---

## 14. Example operational inference contract

Input:

```json
{
  "schema_version": "vibe21.predict_operational.v1",
  "building_id": "bldg_building_100",
  "model_id": "demand_now_v1",
  "interval_minutes": 15,
  "history": [
    {
      "timestamp_utc": "2026-07-25T12:00:00Z",
      "outdoor_air_temp_f": 88.2,
      "zone_temp_f": 73.4,
      "sat_f": 55.1,
      "fan_kw": 41.8,
      "occupied": true,
      "building_kw": 412.0
    }
  ]
}
```

Output:

```json
{
  "schema_version": "vibe21.prediction.v1",
  "model_id": "demand_now_v1",
  "model_version": "1.0.0",
  "predicted_kw": 425.3,
  "interval_minutes": 15,
  "derived_interval_kwh": 106.325,
  "units": {
    "predicted_kw": "kW",
    "derived_interval_kwh": "kWh"
  },
  "domain_status": "IN_DOMAIN",
  "warnings": []
}
```

---

## 15. Example scenario-surrogate contract

Input:

```json
{
  "schema_version": "vibe21.predict_scenario.v1",
  "building_id": "bldg_building_100",
  "scenario": {
    "weather_id": "amy_2025",
    "cooling_capacity_multiplier": 0.8,
    "fan_power_multiplier": 1.0,
    "outdoor_air_fraction": 0.1,
    "economizer_enabled": false,
    "occupied_start_hour": 6.0,
    "occupied_end_hour": 19.0,
    "cooling_setpoint_f": 74.0
  }
}
```

Output:

```json
{
  "schema_version": "vibe21.scenario_prediction.v1",
  "model_bundle_id": "scenario_surrogate_v1",
  "annual_electricity_kwh": 1425000.0,
  "peak_electric_demand_kw": 612.4,
  "annual_natural_gas_therm": 18400.0,
  "unmet_hours": 213.0,
  "domain_status": "IN_DOMAIN",
  "warnings": [],
  "prediction_kind": "ML_SURROGATE_OF_ENERGYPLUS"
}
```

---

## 16. Model status lifecycle

```text
EXPERIMENTAL
VALIDATED_SYNTHETIC
VALIDATED_REAL_HOLDOUT
APPROVED_DEMO
RETIRED
REJECTED
```

`APPROVED_DEMO` means approved for the declared demonstration purpose; it does not mean design-grade or control-grade.

---

## 17. Explainability

Prefer lightweight explanations for the web demo:

- global permutation importance generated offline;
- model-native feature importance where meaningful;
- partial dependence generated offline for selected variables;
- residual plots;
- scenario sensitivity charts.

SHAP may be added offline when useful, but the first PythonAnywhere runtime should not require a heavy explainability dependency merely to serve predictions.

---

## 18. Security note on joblib/pickle

`joblib` is appropriate for trusted scikit-learn artifacts, but deserialization can execute code. Never accept arbitrary model uploads from public users and load them. The deploy bundle uses only pre-approved model files produced by the offline training pipeline.
