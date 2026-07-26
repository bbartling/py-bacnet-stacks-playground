# Vibe Code App 21 — Physics-Trained ML Digital Twin

Vibe Code App 21 is the deployment and visualization successor to:

- **Vibe Code App 19** — real BAS historian ingestion, equipment/point mapping, schedules, weather reconciliation, Open-FDD analytics, RCx findings, and engineering exports.
- **Vibe Code App 20 / OpenFDD WattLab** — EnergyPlus model creation, autosizing, calibration/validation, scenario simulation, ECM screening, and independent HVAC engineering benchmarks.
- **Vibe Code App 21** — offline synthetic-data generation and ML training, a lightweight Flask inference backend, React engineering UI, and a Unity WebGL digital-twin view.

This directory is intentionally **specification-only**. It contains no production implementation, no trained model, and no generated Unity build.

## Revised product vision

Vibe 21 is not an EnergyPlus server. EnergyPlus remains the offline physics engine used to create and validate training data.

The deployable Vibe 21 demo is intentionally lightweight:

```text
Vibe 19 BAS/FDD evidence
          +
Vibe 20 calibrated/validated EnergyPlus model
          │
          ▼
OFFLINE simulation farm
weather × schedules × controls × faults × capacities × envelope uncertainty
          │
          ▼
feature-engineered Parquet dataset
          │
          ▼
scikit-learn training + blocked validation
          │
          ▼
trusted model bundle
.joblib + model cards + feature/target schemas + validation evidence
          │
          ▼
PythonAnywhere Flask WSGI app
├── REST inference API
├── compiled React SPA
└── compiled Unity WebGL build
```

## The two ML twins

Vibe 21 should not force every engineering question into one model.

### 1. Operational time-series twin

Consumes a current BAS/weather row plus a required lookback window and predicts operational quantities such as:

- whole-building electric demand, kW;
- 15-minute / 1-hour demand forecast, kW;
- selected virtual sensors such as cooling tons or equipment load;
- optional fault probabilities.

For a fixed interval, electrical energy is derived from predicted average demand when physically appropriate:

```text
interval_kWh = predicted_average_kW × interval_hours
```

For example, a 15-minute interval uses `interval_hours = 0.25`.

### 2. Scenario surrogate twin

Consumes EnergyPlus scenario parameters and predicts whole-scenario outcomes such as:

- annual/monthly electricity, kWh;
- annual gas, therm or kWh-equivalent;
- peak electric demand, kW;
- unmet hours;
- comfort metrics;
- optional end-use energy.

This is the fast model used by React/Unity sliders to approximate previously learned EnergyPlus behavior without executing EnergyPlus on PythonAnywhere.

## Deployment goal

The final implementation should produce a human-uploadable bundle that can be unzipped on PythonAnywhere and served from one web application:

```text
vibe21_deploy_bundle/
├── flask_app.py
├── requirements.txt
├── vibe21/
├── models/
├── static/
│   ├── react/
│   └── unity/
├── manifests/
└── README_PYTHONANYWHERE.md
```

The Unity work is performed outside this Python project using Unity + Unity MCP/AI tooling. The Unity agent exports a WebGL build; the human copies or merges that generated build into the Vibe 21 deployment bundle.

## Fixed first-release choices

- Python 3.
- Flask WSGI backend for the PythonAnywhere demo.
- scikit-learn-first ML stack.
- `joblib` model persistence for trusted local artifacts.
- Pandas or Polars for feature generation; Parquet as the canonical training-table format.
- React for dense engineering UI, forms, model metadata, and Plotly charts.
- Unity WebGL for spatial equipment/zone visualization and scenario interaction.
- SQLite optional for lightweight demo metadata; JSON/Parquet artifacts remain first-class.
- No live EnergyPlus execution on the PythonAnywhere demo.
- No model training in public HTTP requests.
- No BAS commanding.

## Specification files

- [`AGENTS.md`](AGENTS.md) — agent mission, hard boundaries, implementation order, and completion rules.
- [`vibe21_agent_spec/SPEC.md`](vibe21_agent_spec/SPEC.md) — full product and architecture specification.
- [`vibe21_agent_spec/ML_ARCHITECTURE.md`](vibe21_agent_spec/ML_ARCHITECTURE.md) — feature/target design, multi-input/multi-output strategy, validation, and model registry.
- [`vibe21_agent_spec/PYTHONANYWHERE_DEPLOYMENT.md`](vibe21_agent_spec/PYTHONANYWHERE_DEPLOYMENT.md) — deploy-bundle contract.
- [`vibe21_agent_spec/UNITY_WEBGL_HANDOFF.md`](vibe21_agent_spec/UNITY_WEBGL_HANDOFF.md) — Unity MCP/agent handoff and browser bridge.
- [`vibe21_agent_spec/SCHEMAS.md`](vibe21_agent_spec/SCHEMAS.md) — initial JSON contracts.

## Status

**Revised planning scaffold only. No application code is included in this package.**
