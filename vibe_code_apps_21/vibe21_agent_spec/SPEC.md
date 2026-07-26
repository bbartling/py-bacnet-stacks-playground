# Vibe 21 Agentic AI Specification — Physics-Trained ML + Unity Digital Twin

**Project:** OpenFDD Physics-Trained ML Digital Twin  
**Directory:** `vibe_code_apps_21`  
**Status:** revised planning specification  
**Implementation state:** no code in this package  
**Primary predecessors:** `vibe_code_apps_19`, `vibe_code_apps_20`

---

## 1. Purpose

Vibe 21 is the final deployable demonstration layer for the Vibe 19 → Vibe 20 workflow.

It combines:

- real building evidence from Vibe 19;
- calibrated/validated or explicitly conceptual EnergyPlus physics from Vibe 20;
- offline synthetic scenario generation;
- engineered ML training datasets;
- lightweight scikit-learn surrogate models;
- Flask inference APIs;
- a React engineering shell;
- and Unity WebGL spatial visualization.

Vibe 21 is **not** primarily an online EnergyPlus runner. EnergyPlus is used offline as a physics-based synthetic-data generator and validation reference. The public/demo runtime serves pre-trained models.

---

## 2. Relationship to Vibe 19 and Vibe 20

### 2.1 Vibe 19 contribution

Vibe 19 already establishes useful operational contracts including:

- `openfdd_package_v1` historian packages;
- `wattlab_dump_v3` export to Vibe 20;
- equipment typing and logical role mapping;
- occupancy/calendar information;
- BAS vs web-weather handling;
- FDD rule results and explicit skip states;
- RCx findings;
- operating signatures;
- sensor statistics and diurnal profiles;
- setpoints;
- motor/runtime analytics;
- optional shared equipment telemetry;
- utility bills when available.

Vibe 21 must consume structured Vibe 19/Vibe 20 artifacts, not screenshots or Streamlit session state.

### 2.2 Vibe 20 contribution

Vibe 20 establishes:

- EnergyPlus model creation and management;
- sparse-building modeling workflow;
- autosizing with explicit provenance;
- scenario/ECM patching;
- AMY/TMY weather handling;
- calibration and holdout validation posture;
- result parsing;
- peak demand extraction;
- annual electricity/gas results;
- independent HVAC engineering benchmark calculations;
- reproducibility hashes and run manifests.

Vibe 21 must preserve the distinction between conceptual, calibrated, and validated physics models.

### 2.3 Vibe 21 contribution

Vibe 21 adds:

- an offline simulation-farm contract;
- a versioned feature-engineering contract;
- ML dataset manifests;
- scikit-learn candidate/champion training;
- grouped and blocked validation;
- operational demand models;
- energy aggregation and scenario-energy surrogate models;
- model registry/model cards;
- lightweight Flask inference;
- React + Plotly web UI;
- Unity WebGL visualization and scenario interaction;
- PythonAnywhere deployment bundle generation.

---

## 3. Revised core architecture

```text
                        REAL BUILDING
                             │
                             ▼
                 VIBE 19 / Open-FDD evidence
        BAS + mapping + weather + FDD + RCx + utility
                             │
                             ▼
                      VIBE 20 WattLab
          EnergyPlus baseline + calibration + scenarios
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
      calibrated model              engineering benchmark
              │
              ▼
      OFFLINE SIMULATION FARM
 weather × schedules × controls × faults × capacities × uncertainty
              │
              ▼
         raw run artifacts
              │
              ▼
   FEATURE ENGINEERING / LABELING
              │
              ▼
     partitioned Parquet datasets
              │
              ▼
       SCIKIT-LEARN TRAINING
     baselines + candidate models
              │
              ▼
   grouped/blocked validation gates
              │
              ▼
         APPROVED MODEL BUNDLE
  joblib + schemas + cards + hashes + metrics
              │
              ▼
        PYTHONANYWHERE / FLASK
      ┌──────────────┼──────────────┐
      ▼              ▼              ▼
   REST API      React/Plotly     Unity WebGL
```

---

## 4. Product modes

### 4.1 Operational replay/live-safe mode

Given a safe replay stream or read-only BAS-derived feature window, predict:

- building demand kW;
- optional future demand horizons;
- derived interval energy kWh;
- optional virtual sensors;
- optional fault probabilities.

### 4.2 Scenario preview mode

Given approved scenario sliders/inputs, predict EnergyPlus-like outcomes instantly:

- annual/monthly electricity;
- peak kW;
- annual gas;
- unmet hours;
- comfort metrics;
- selected end uses.

This is an ML surrogate of the sampled EnergyPlus scenario space, not a new EnergyPlus simulation.

### 4.3 Evidence comparison mode

Display:

- actual BAS/meter data when available;
- ML prediction;
- residual;
- EnergyPlus reference result when applicable;
- independent Vibe 20 benchmark;
- source/provenance/status.

---

## 5. Non-goals for first release

The first release does not require:

- direct BAS writes or control;
- online EnergyPlus on PythonAnywhere;
- EnergyPlus co-simulation;
- online model training;
- deep learning;
- Kubernetes;
- Redis/Celery queues;
- arbitrary IDF editing in the browser;
- arbitrary user-uploaded ML models;
- design-grade load calculations;
- autonomous closed-loop optimization;
- photorealistic Unity rendering;
- a claim that synthetic holdout accuracy equals real-building accuracy.

---

## 6. Fixed technology posture

### 6.1 Offline physics/training stack

Preferred:

- Python;
- Vibe 20 EnergyPlus execution path;
- Pandas and/or Polars;
- Parquet;
- scikit-learn;
- joblib;
- optional DuckDB for dataset exploration/aggregation;
- optional Plotly/Jupyter for offline diagnostics.

### 6.2 Deployment backend

Flask is mandatory for the first PythonAnywhere demo.

Flask responsibilities:

- JSON API routing;
- request validation/orchestration;
- feature compilation for inference;
- model registry loading;
- prediction;
- provenance/warning responses;
- serving/bridging the application shell as needed.

The deployed backend does not run EnergyPlus or training jobs.

### 6.3 Frontend

React is preferred and should own:

- model status/metadata;
- exact engineering values;
- forms/sliders;
- selected-period data;
- Plotly charts;
- residual/actual/predicted comparisons;
- warnings and provenance;
- scenario controls.

Unity WebGL is embedded as a first-class spatial view.

---

## 7. Canonical identity

Stable IDs are mandatory across Vibe 19, Vibe 20, ML datasets, Flask, React, and Unity.

Minimum identity types:

- building;
- equipment;
- point/role;
- zone;
- physics model;
- simulation;
- scenario;
- ML dataset;
- feature schema;
- target schema;
- ML model;
- Unity object binding.

Display names are not stable identifiers.

---

## 8. Provenance classes

Minimum classes:

```text
MEASURED
MAPPED_BAS
WEB_WEATHER
UTILITY_RECORD
DRAWING
NAMEPLATE
USER_ENTERED
AUTOSIZED
INFERRED
ARCHETYPE_DEFAULT
LIBRARY_DEFAULT
CALIBRATED
VALIDATED
ENERGYPLUS_SIMULATED
ML_PREDICTED
DERIVED
UNKNOWN
```

No transformation may relabel simulated or predicted values as measured.

---

## 9. Vibe 19 handoff contract

Vibe 21 should preferentially build from the same structured evidence Vibe 20 already consumes.

Relevant Vibe 19/Vibe 20 seed artifacts include:

- `MANIFEST.json`;
- `model_seed.json`;
- `schedule_inference.json`;
- `operating_signatures.csv`;
- `sensor_stats_all.csv`;
- `sensor_diurnal_24h.csv`;
- `setpoints.csv`;
- `mech_cooling_oat_bins.csv`;
- `mech_cooling_coverage.csv`;
- `motor_hours.csv`;
- `fdd_summary.csv`;
- `fdd_findings.csv`;
- `weather_observed.csv`;
- `utility_bills.csv`;
- `topology.csv`;
- `data_model.csv`;
- optional `telemetry/*.csv`.

The exact source is versioned in the Vibe 21 dataset manifest.

---

## 10. Vibe 20 handoff contract

Vibe 21 consumes Vibe 20 artifacts sufficient to establish:

- EnergyPlus model identity/hash;
- weather identity/hash;
- EnergyPlus version;
- calibration status;
- calibration period and metrics;
- validation/holdout status;
- scenario parameters;
- simulation ID;
- annual electricity/gas;
- peak kW;
- selected timeseries outputs;
- unmet/comfort outputs;
- diagnostics/severe/fatal counts;
- independent benchmark result where applicable.

If a Vibe 20 model is only conceptual, all downstream Vibe 21 synthetic/model artifacts remain clearly conceptual until later evidence upgrades them.

---

## 11. Simulation farm

### 11.1 Goal

Use one trusted Vibe 20 physics model as a controlled building laboratory.

### 11.2 Scenario families

Sample defensible ranges for:

- weather;
- occupancy/schedules;
- internal loads;
- setpoints;
- ventilation;
- economizer behavior;
- SAT/duct-static/control strategies;
- fan/pump power or sizing;
- chiller/boiler capacity and efficiency;
- envelope/infiltration uncertainty;
- faults such as sensor bias, stuck damper, leaking valve, bad schedule;
- calibrated parameter uncertainty.

### 11.3 Scenario manifest

Every simulation records exact parameter values plus:

- `simulation_id`;
- `scenario_id`;
- random/quasi-random seed;
- physics model hash;
- weather hash;
- output schema;
- EnergyPlus status/diagnostics;
- feature/target eligibility.

Failed EnergyPlus runs remain traceable but are not silently treated as valid training rows.

---

## 12. Raw synthetic timeseries

Canonical raw fields should be selected based on the actual model and mapped equipment, but expected categories include:

```text
timestamp
weather
occupancy
zone temperatures/setpoints
AHU SAT/setpoint
airflow
damper/valve state
fan power
cooling/heating load
chiller/plant power
whole-building electricity/demand
natural gas
fault labels
control strategy
simulation_id
scenario_id
```

Do not request every EnergyPlus output variable by default. The dataset should be intentional and manageable.

---

## 13. Feature engineering

The feature compiler converts raw physics/BAS rows into canonical ML features.

Examples:

```text
zone_temp_error
sat_error
oat_zone_delta
oat_sat_delta
damper_saturation_pct
after_hours_runtime
economizer_opportunity
simultaneous_heat_cool
fan_kw_per_cfm
cooling_kw_per_ton
rolling_kw_mean_15m
rolling_kw_std_60m
kw_rate_of_change
zone_temp_slope
sat_slope
lag_kw_15m
lag_kw_60m
occupied
hour_sin/hour_cos or equivalent time encoding
```

No feature may use values occurring after the prediction timestamp.

---

## 14. ML model families

### 14.1 Operational demand

Default target:

```text
building_kw_avg_interval
```

Optional separate models for:

```text
building_kw_t_plus_15m
building_kw_t_plus_60m
```

Candidates:

- persistence baseline;
- Ridge;
- HistGradientBoostingRegressor;
- RandomForestRegressor;
- ExtraTreesRegressor.

### 14.2 Energy

If demand target is average kW for a regular interval:

```text
interval_kwh = predicted_kw * interval_hours
```

This derived value is preferred over a redundant second ML target for the same interval.

For monthly/annual scenario energy, use dedicated scenario-level regression models or a validated multi-output surrogate.

### 14.3 Scenario surrogate

Targets:

- annual/monthly electricity;
- peak kW;
- annual gas;
- unmet hours;
- comfort violations;
- selected end uses.

### 14.4 FDD classifier

Optional separate classifier for labels intentionally injected into synthetic scenarios.

### 14.5 Virtual sensors

Optional models for quantities absent from BAS but available from EnergyPlus ground truth, such as:

- cooling tons;
- heating load;
- equipment load fraction;
- estimated airflow;
- estimated occupancy where defensibly framed.

---

## 15. Multi-input / multi-output design

### 15.1 Multi-input

Yes: all primary ML models are naturally **multi-input** models. A feature row/window contains many columns/inputs simultaneously.

Example:

```text
X = [
  OAT,
  humidity,
  occupied,
  hour,
  zone_temp,
  zone_setpoint,
  SAT,
  SAT_setpoint,
  airflow,
  fan_kw,
  lag_kw_15m,
  rolling_kw_60m,
  ...
]
```

### 15.2 Multi-output

Possible but not mandatory.

A model could predict:

```text
y = [annual_kwh, peak_kw, annual_gas_therm, unmet_hours]
```

RandomForestRegressor can support multi-output directly; single-target estimators may be wrapped with `MultiOutputRegressor`.

However, Vibe 21 defaults to separate champion models per target/horizon so each target can be validated and replaced independently.

### 15.3 Important demand/energy relationship

Do not train two independent models to predict average kW and the same interval kWh unless needed. Their outputs could conflict.

Prefer:

```text
ML → average kW
math → interval kWh
```

Use a distinct energy model only for a different horizon/problem such as monthly or annual energy.

---

## 16. Training dataset layout

Suggested partitioned dataset:

```text
ml_data/
├── operational/
│   ├── features.parquet
│   └── dataset_manifest.json
├── scenario/
│   ├── scenario_features_targets.parquet
│   └── dataset_manifest.json
└── catalogs/
    ├── feature_schema.json
    └── target_schema.json
```

Large datasets may be partitioned by building, simulation batch, weather year, or other stable dimensions.

---

## 17. Leakage controls

Mandatory tests assert:

- no target column appears in features;
- no future timestep enters lag/rolling features;
- no whole-day peak feature is used for a timestamp before that day is complete;
- `simulation_id` groups do not cross train/test;
- real BAS test windows are contiguous and future-held-out;
- scaling/encoding is fitted only on training data;
- feature compiler behavior is deterministic.

---

## 18. Validation gates

Every candidate reports metrics by target and validation domain.

Minimum:

- synthetic train;
- synthetic validation;
- synthetic grouped test;
- real BAS/meter holdout when available;
- engineering sanity tests.

A candidate may be excellent on synthetic test and still be rejected because it fails real BAS holdout or extreme-weather checks.

---

## 19. Model persistence

Persist the complete fitted preprocessing/model object when appropriate:

```text
joblib model artifact
+
feature schema
+
target schema
+
training manifest
+
validation report
+
model card
+
checksums
```

Because joblib/pickle deserialization is unsafe for untrusted files, the public demo never accepts arbitrary user model uploads.

---

## 20. Flask runtime architecture

```text
Flask WSGI app
├── health/model registry
├── canonical feature compiler
├── operational prediction service
├── scenario surrogate service
├── optional FDD/virtual-sensor service
├── React asset routes/static mapping
└── Unity asset routes/static mapping
```

Models are loaded once and cached per web worker/process.

---

## 21. API

First-release API:

```text
GET  /api/v1/health
GET  /api/v1/twin/manifest
GET  /api/v1/building
GET  /api/v1/equipment
GET  /api/v1/unity-bindings
GET  /api/v1/models
POST /api/v1/predict/operational
POST /api/v1/predict/scenario
```

Optional later:

```text
POST /api/v1/predict/faults
POST /api/v1/predict/virtual-sensor
```

No `/simulations` job API is required for the PythonAnywhere demo because simulations are offline.

---

## 22. Operational prediction response requirements

Return:

- model ID/version;
- prediction timestamp;
- predicted kW;
- interval duration;
- derived interval kWh;
- optional prediction horizons;
- domain status;
- feature coverage;
- warnings;
- provenance.

When actual meter data is supplied for comparison, also return:

```text
actual_kw
predicted_kw
residual_kw
residual_percent
```

Do not call residual energy waste without a documented baseline interpretation.

---

## 23. Scenario prediction response requirements

Return:

- surrogate model bundle ID;
- exact normalized scenario input;
- annual/monthly kWh as available;
- peak kW;
- gas;
- comfort/unmet metrics;
- training-domain status;
- warnings;
- clear label `ML_SURROGATE_OF_ENERGYPLUS`.

When comparing to a baseline scenario, compute deltas explicitly and identify both model/scenario IDs.

---

## 24. React shell

Recommended layout:

```text
┌───────────────────────────────────────────────────────────────┐
│ Building | data source | physics status | ML model status     │
├───────────────────┬──────────────────────────┬────────────────┤
│ Scenario / Inputs │ Unity WebGL              │ Engineering    │
│                   │                          │ Results        │
│ occupancy         │ zones/equipment          │ actual/pred KW │
│ setpoints         │ select equipment         │ interval kWh   │
│ capacity          │ color by state           │ annual kWh     │
│ ventilation       │ spatial scenario delta   │ peak kW        │
│ economizer        │                          │ gas/comfort    │
│ weather           │                          │ Plotly         │
│ [Predict]         │                          │ provenance     │
└───────────────────┴──────────────────────────┴────────────────┘
```

React is authoritative for dense engineering values and provenance presentation.

---

## 25. Unity WebGL

Unity is used for spatial context:

- building/floor/zone selection;
- equipment selection;
- color by fault/comfort/load/data status;
- scenario-result coloring;
- animated/replay state where useful.

Unity consumes Flask APIs and stable binding IDs.

Unity does not hold calibration state, trained models, or authoritative scenario definitions only in PlayerPrefs/browser memory.

---

## 26. Unity external-agent workflow

Expected human/agent workflow:

1. Python/repo agent freezes API and binding schemas.
2. Unity MCP/AI agent reads the schema/handoff document.
3. Unity agent creates/updates the Unity project externally.
4. Unity agent exports a WebGL build.
5. Unity agent zips the built web assets.
6. Human or packaging agent merges build under `static/unity/`.
7. Deploy-bundle validator checks required files and hashes.
8. Final PythonAnywhere zip is produced.

---

## 27. PythonAnywhere deployment

The deployment target is one Flask WSGI application.

Requirements:

- no `app.run()` during WSGI import;
- virtualenv-based dependencies;
- compiled React assets;
- compiled Unity WebGL assets;
- trusted model files only;
- same-origin API calls;
- small predictable memory footprint;
- static file strategy tested on target hosting.

For Unity, prefer Decompression Fallback or another tested configuration that does not depend on custom content-encoding server rules unavailable to the human.

---

## 28. Security

- Never load untrusted pickle/joblib artifacts.
- Never accept executable paths from web input.
- Never expose secrets in client bundles.
- Cap request/history sizes.
- Validate timestamps/units/ranges.
- Do not expose private raw historian data in a public demo.
- Add authentication before hosting sensitive customer-specific twins.
- Rate-limit prediction endpoints when appropriate.
- Treat all client-provided entity IDs/scenario fields as untrusted.

---

## 29. Observability

Minimum runtime events:

- app/model registry loaded;
- model hash validation pass/fail;
- prediction request accepted/rejected;
- domain warning emitted;
- prediction latency;
- prediction failure;
- React/Unity bootstrap failure where detectable.

Offline pipeline records:

- simulation batch started/completed;
- failed EnergyPlus runs;
- dataset build;
- training run;
- split definition;
- candidate metrics;
- champion selection;
- bundle export.

---

## 30. Testing strategy

### 30.1 Unit

- feature formulas;
- lag/rolling windows;
- kW → kWh integration;
- unit conversions;
- domain checks;
- model registry hashes;
- scenario normalization.

### 30.2 Leakage

- grouped simulation split;
- no future rows in features;
- no target contamination;
- preprocessing fit only on train.

### 30.3 Model

- deterministic golden fixture;
- baseline comparisons;
- metric thresholds;
- artifact reload reproduces predictions;
- runtime dependency compatibility.

### 30.4 Flask

- WSGI import;
- health endpoint;
- valid/invalid prediction payloads;
- model unavailable response;
- history-limit enforcement.

### 30.5 Frontend/Unity

- React route loads;
- same-origin API request;
- Unity build files resolve;
- Unity binding resolves;
- one scenario interaction returns and renders energy + peak demand.

### 30.6 Deployment

- clean unzip;
- install requirements;
- import application;
- verify checksums;
- run golden operational request;
- run golden scenario request.

---

## 31. Milestone plan

### Milestone 0 — specification and contracts

- freeze this spec;
- freeze feature/target schemas;
- freeze Vibe 19/20 handoff assumptions;
- define Unity binding contract.

### Milestone 1 — tiny offline ML proof

- use a tiny EnergyPlus fixture;
- generate multiple scenarios;
- build Parquet;
- train demand model;
- derive interval kWh;
- train scenario annual-kWh and peak-kW models;
- prove grouped validation.

### Milestone 2 — Building 100-style model family

- consume Vibe 19 WattLab dump;
- consume Vibe 20 calibrated/validated model artifacts;
- generate realistic scenario ranges;
- build operational and scenario datasets;
- compare candidate models.

### Milestone 3 — Flask inference

- registry/model loading;
- feature compiler;
- operational endpoint;
- scenario endpoint;
- model cards/domain warnings;
- golden tests.

### Milestone 4 — React

- engineering shell;
- actual/predicted/residual charts;
- demand + energy cards;
- scenario sliders;
- model/provenance panel.

### Milestone 5 — Unity

- external Unity MCP build;
- canonical bindings;
- selected object details;
- scenario response coloring;
- WebGL deployment smoke.

### Milestone 6 — PythonAnywhere bundle

- merge React build;
- merge Unity build;
- include trusted ML models;
- create deploy manifest/checksums;
- create exact PythonAnywhere instructions;
- smoke test final zip.

---

## 32. Definition of done — first usable release

The first release is complete when:

- Vibe 19 evidence can be traced into the Vibe 20/Vibe 21 project identity;
- a declared Vibe 20 physics model generated the synthetic dataset;
- synthetic scenarios and dataset have reproducible manifests/hashes;
- demand model predicts kW on grouped holdout data;
- interval kWh is derived consistently from predicted average kW;
- scenario surrogate predicts at minimum annual kWh and peak kW;
- candidate models were compared to simple baselines;
- validation is grouped/blocked rather than random-row leakage;
- model artifacts reload reproducibly;
- Flask serves model inference without EnergyPlus or training;
- React displays predictions, residuals, energy, demand, status, and provenance;
- Unity WebGL loads and resolves canonical equipment/zone bindings;
- Unity or React can submit a scenario and display surrogate energy/peak-demand results;
- final bundle unzips into a PythonAnywhere-friendly structure;
- WSGI import works;
- all tests/checksums pass;
- limitations clearly state that the deployed ML twin is a surrogate whose quality depends on Vibe 20 physics and real-building validation.

---

## 33. Guiding principle

A Vibe 21 result is trustworthy only when a user can answer:

- What came from the real BAS?
- What came from utility/weather evidence?
- What came from Vibe 19 analytics?
- What EnergyPlus model generated the synthetic data?
- Was that model conceptual, calibrated, or validated?
- Which scenario generated this training row?
- Which features were available at prediction time?
- Was any future information leaked?
- Which model/version made the prediction?
- What was its held-out performance?
- Is this request inside the training domain?
- Is kWh measured, predicted directly, or derived from kW?
- Which Unity object maps to which engineering entity?
- Can the artifact hashes and prediction be reproduced?

If those questions cannot be answered, the feature is incomplete.

---

## 34. Reference implementation posture

Current public documentation used when revising this specification:

- scikit-learn multi-output regression documentation: https://scikit-learn.org/stable/modules/multiclass.html#multioutput-regression and API docs for `MultiOutputRegressor` / `RandomForestRegressor`.
- PythonAnywhere Flask deployment guidance: https://help.pythonanywhere.com/pages/Flask/
- PythonAnywhere static mapping guidance: https://help.pythonanywhere.com/pages/StaticFiles/
- Unity WebGL compressed-build/decompression-fallback guidance: https://docs.unity3d.com/Manual/webgl-deploying.html (or current equivalent for the selected Unity version).

Pin exact package/Unity versions in the eventual implementation and record them in build manifests.
