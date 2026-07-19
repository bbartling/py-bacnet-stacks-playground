# Vibe 21 Agentic AI Specification

**Project:** OpenFDD EnergyPlus Unity Digital Twin Studio  
**Directory:** `vibe_code_apps_21`  
**Status:** planning specification  
**Implementation state:** no code  
**Primary predecessors:** `vibe_code_apps_19`, `vibe_code_apps_20`

---

## 1. Purpose

Vibe 21 joins operational building data, fault detection, physics simulation, engineering calculations, and spatial visualization into one reproducible workflow.

The application is not merely a 3D building viewer. It is an engineering digital-twin studio whose visual state must be traceable to:

- measured BAS data;
- explicit equipment and point mappings;
- weather data;
- Open-FDD analytics;
- an EnergyPlus model;
- documented assumptions;
- scenario patches;
- simulation outputs;
- local HVAC benchmark calculations;
- and a versioned result manifest.

The product must support incomplete existing-building records. It may estimate missing values, autosize systems, or use archetype defaults, but all such values must remain visible and attributable.

---

## 2. Relationship to Vibe 19 and Vibe 20

### 2.1 Vibe 19 contribution

Vibe 19 provides the conceptual reference for:

- `openfdd_package_v1`-style building packages;
- historian CSV ingestion;
- equipment and logical-role mapping;
- typed equipment;
- occupancy schedules;
- BAS and web-weather reconciliation;
- rule execution states;
- FDD findings;
- RCx charts;
- engineering notes;
- session restore;
- and report generation.

Vibe 21 must consume Vibe 19 outputs through a defined adapter or shared schema rather than scraping Streamlit state.

### 2.2 Vibe 20 contribution

Vibe 20 provides the conceptual reference for:

- EnergyPlus model management;
- weather/EPW resolution;
- autosizing;
- scenario construction;
- IDF or epJSON patching;
- calibration;
- ECM definitions;
- local HVAC calculation benchmarks;
- run manifests;
- result parsing;
- and agentic simulation loops.

Vibe 21 must preserve an independent comparison between EnergyPlus and the local engineering benchmark.

### 2.3 Vibe 21 addition

Vibe 21 adds:

- a stable backend API;
- asynchronous simulation jobs;
- durable project and artifact storage;
- a browser application shell;
- Unity WebGL serving;
- Unity-to-building identity bindings;
- spatial result visualization;
- scenario controls;
- job progress and history;
- baseline/scenario comparison;
- and optional Streamlit analyst views.

---

## 3. User stories

### 3.1 Existing-building analyst

An analyst uploads a prepared building package, confirms mappings and schedules, reviews Vibe 19 findings, builds an estimated EnergyPlus model, and sees all uncertain model inputs listed before simulation.

### 3.2 Undersized-system experiment

An analyst begins with an autosized baseline, creates a scenario with a 70% cooling-capacity multiplier, extends operating hours, disables outdoor-air ventilation, selects extreme-weather periods, runs the model, and compares energy, peak demand, unmet hours, and zone comfort.

### 3.3 Unity digital-twin viewer

A user clicks an AHU in Unity and sees:

- canonical equipment ID;
- mapped BAS points;
- current or selected-period state;
- fault findings;
- runtime;
- EnergyPlus object bindings;
- baseline and scenario results;
- related zones and VAVs;
- provenance and confidence.

### 3.4 Engineering benchmark comparison

A simulation result displays EnergyPlus values beside independent spreadsheet-derived or library-derived calculations, including percentage difference and an explanation of mismatched assumptions.

### 3.5 Agent-driven workflow

An agent may create a project, validate inputs, propose assumptions, create scenarios, submit simulations, inspect diagnostics, and generate a report. It may not hide assumptions, bypass validation, or silently accept severe EnergyPlus errors.

---

## 4. Non-goals for the first release

The first release does not require:

- millisecond real-time control;
- direct BAS commanding;
- multiplayer collaborative editing;
- photorealistic rendering;
- arbitrary IDF editing in the browser;
- a general-purpose building-model authoring tool;
- live EnergyPlus co-simulation;
- Kubernetes;
- multiple queue technologies at once;
- or automatic claims that an estimated model is calibrated.

---

## 5. High-level architecture

```text
same-origin web address
│
├── /
│   ├── web shell
│   ├── Unity WebGL loader/build
│   └── static assets
│
├── /api/v1/
│   ├── projects
│   ├── packages
│   ├── buildings
│   ├── equipment
│   ├── analytics
│   ├── models
│   ├── scenarios
│   ├── simulations
│   ├── comparisons
│   └── reports
│
└── /results/
    └── immutable or content-addressed artifacts
```

Required FastAPI backend and conceptual services:

```text
API process
├── validation
├── authorization
├── project records
├── scenario records
└── job submission/status
        │
        ▼
queue abstraction
        │
        ▼
simulation worker
├── stage input files
├── patch derived model
├── run EnergyPlus
├── preserve diagnostics
├── parse outputs
├── run HVAC benchmark
├── build comparisons
└── publish result manifest
```

---

## 6. Technology posture

### 6.1 Backend

FastAPI is mandatory.

The required backend foundation is:

- FastAPI for HTTP routing, dependency injection, exception handling, and OpenAPI generation;
- Pydantic v2 for request, response, configuration, event, manifest, and persisted schema validation;
- Uvicorn for local and development ASGI serving;
- framework-neutral service modules behind the API layer for building packages, analytics, scenarios, jobs, EnergyPlus execution, result parsing, benchmarks, and reports.

No implementation may introduce Flask, Django, Sanic, Litestar, or another competing backend framework. Streamlit is a client of the FastAPI API and must never own core domain execution.

FastAPI's generated OpenAPI document is the canonical machine-readable API contract. Unity, the browser shell, Streamlit, CLI tools, and agents must consume the same versioned contract.

Domain meaning must remain independent of FastAPI request objects, but the implementation stack itself is intentionally standardized.

### 6.2 Queue

Development must support a simple local queue or worker.

Deployment may use Redis with RQ, Dramatiq, Celery, or another justified worker system.

Redis may be used for:

- pending job coordination;
- worker leasing;
- transient stage/status updates;
- caching;
- rate limiting;
- and pub/sub notifications.

Redis must not be the sole durable store for projects, scenarios, final job records, or simulation artifacts.

### 6.3 Storage

A local deployment may use:

- SQLite for metadata;
- local filesystem for artifacts.

A larger deployment may use:

- PostgreSQL for metadata;
- S3-compatible object storage for artifacts.

The storage interface must preserve identical domain behavior.

### 6.4 Frontend

The final shell may be React, Vue, Svelte, plain TypeScript, or another conventional web framework.

Unity WebGL is embedded as a first-class view.

Plotly is preferred for engineering charts.

### 6.5 Streamlit

Streamlit may be:

- a prototype shell;
- an internal analyst console;
- a model calibration workbench;
- a report-review interface;
- or an embedded-Unity demonstration.

Streamlit may call the same APIs as other clients. It must not become the only route to core functionality.

---

## 7. Canonical identity model

Every entity that crosses Vibe 19, Vibe 20, the API, and Unity requires a stable identifier.

Minimum entity types:

- organization;
- site;
- building;
- project;
- data package;
- equipment;
- point;
- zone;
- EnergyPlus model;
- EnergyPlus object binding;
- scenario;
- simulation job;
- result set;
- artifact;
- report;
- Unity object binding.

Display names are mutable and not identifiers.

Example:

```json
{
  "schema_version": "vibe21.identity.v1",
  "building_id": "bldg_building_100",
  "equipment_id": "equip_ahu_1",
  "display_name": "AHU-1",
  "equipment_type": "AHU",
  "source_refs": {
    "vibe19_equipment_id": "AHU_1",
    "energyplus_object": "AirLoopHVAC:AHU_1",
    "unity_object_key": "Building100/AHU_1"
  }
}
```

---

## 8. Provenance and assumptions

Every model input must use one of these provenance classes:

- `MEASURED`
- `MAPPED_BAS`
- `DRAWING`
- `NAMEPLATE`
- `UTILITY_RECORD`
- `USER_ENTERED`
- `AUTOSIZED`
- `INFERRED`
- `ARCHETYPE_DEFAULT`
- `LIBRARY_DEFAULT`
- `CALIBRATED`
- `DERIVED`
- `UNKNOWN`

Each assumption record includes:

```json
{
  "assumption_id": "asm_...",
  "field_path": "hvac.air_loops.AHU_1.cooling_capacity_w",
  "value": 123456.0,
  "units": "W",
  "provenance": "AUTOSIZED",
  "method": "EnergyPlus sizing run",
  "confidence": 0.72,
  "source_artifact_ids": [],
  "created_by": "agent-or-user-id",
  "created_at": "ISO-8601 timestamp",
  "notes": "No design schedule was available."
}
```

No agent may convert an estimate into a measured value.

---

## 9. Project model

A project groups:

- one building identity;
- one or more building packages;
- one canonical mapping set;
- one or more EnergyPlus baseline models;
- weather files;
- utility targets;
- assumptions;
- scenarios;
- jobs;
- results;
- reports;
- Unity bindings.

The project must be exportable as a portable manifest plus referenced artifacts.

---

## 10. Scenario model

A scenario is immutable after submission to a simulation job.

Required fields:

```json
{
  "schema_version": "vibe21.scenario.v1",
  "scenario_id": "scn_...",
  "project_id": "prj_...",
  "name": "Undersized cooling, no OA, extended hours",
  "base_model_id": "mdl_...",
  "weather_id": "wx_...",
  "simulation_period": {
    "kind": "annual"
  },
  "patches": [],
  "requested_outputs": [],
  "created_by": "user-or-agent",
  "created_at": "ISO-8601 timestamp"
}
```

Supported initial patch families:

- capacity multiplier;
- fan sizing multiplier;
- pump sizing multiplier;
- outdoor-air fraction;
- ventilation enable/disable;
- economizer enable/disable;
- occupied/unoccupied schedules;
- temperature setpoints;
- humidity setpoints;
- equipment availability;
- envelope multipliers;
- infiltration multiplier;
- internal-load multiplier;
- lighting multiplier;
- plug-load multiplier;
- weather selection;
- selected output variables and meters.

Patches are allowlisted, validated, unit-aware, and recorded in a derived-model manifest.

---

## 11. Simulation job lifecycle

Canonical states:

- `CREATED`
- `QUEUED`
- `VALIDATING`
- `STAGING`
- `PATCHING_MODEL`
- `RUNNING_SIZING`
- `RUNNING_ENERGYPLUS`
- `PARSING_RESULTS`
- `RUNNING_BENCHMARKS`
- `BUILDING_COMPARISON`
- `GENERATING_REPORT`
- `COMPLETED`
- `COMPLETED_WITH_WARNINGS`
- `FAILED`
- `CANCEL_REQUESTED`
- `CANCELLED`

A job status response includes:

- job ID;
- scenario ID;
- state;
- stage start time;
- overall timestamps;
- worker identity when applicable;
- warning count;
- error summary;
- artifact links when available.

Do not manufacture a smooth percentage. A client may display stage-based progress.

---

## 12. Initial API contract

### 12.1 FastAPI implementation rules

- All public endpoints live under `/api/v1`.
- Every request body and response body uses an explicit Pydantic v2 model.
- Every route declares a response model and documented error responses.
- API errors use one versioned problem-detail schema.
- Dependency injection supplies authorization, project access, storage, queue, and service dependencies.
- Long-running work is never executed in the route handler.
- Startup and shutdown use FastAPI lifespan handling.
- The OpenAPI schema is exported in CI and checked for unintended breaking changes.
- Unity-facing payloads avoid Python-specific types and use JSON-safe primitives, ISO-8601 timestamps, stable enums, and explicit units.
- API routes orchestrate services; they do not contain EnergyPlus patching or result-parsing logic.
- WebSocket or Server-Sent Events may be added for progress, but polling remains supported.

Suggested endpoints:

```text
GET    /api/v1/health
POST   /api/v1/projects
GET    /api/v1/projects/{project_id}
POST   /api/v1/projects/{project_id}/packages
GET    /api/v1/projects/{project_id}/building
GET    /api/v1/projects/{project_id}/equipment
GET    /api/v1/projects/{project_id}/analytics
POST   /api/v1/projects/{project_id}/models
GET    /api/v1/projects/{project_id}/models
POST   /api/v1/projects/{project_id}/scenarios
GET    /api/v1/projects/{project_id}/scenarios
POST   /api/v1/simulations
GET    /api/v1/simulations/{job_id}
POST   /api/v1/simulations/{job_id}/cancel
GET    /api/v1/simulations/{job_id}/results
GET    /api/v1/simulations/{job_id}/timeseries
POST   /api/v1/comparisons
POST   /api/v1/reports
GET    /api/v1/artifacts/{artifact_id}
GET    /api/v1/projects/{project_id}/unity-bindings
```

Simulation submission returns promptly:

```json
{
  "schema_version": "vibe21.job.v1",
  "job_id": "job_...",
  "scenario_id": "scn_...",
  "state": "QUEUED"
}
```

---

## 13. EnergyPlus execution contract

Each run receives a unique isolated directory.

Required retained artifacts when produced:

- original model reference;
- derived IDF or epJSON;
- scenario manifest;
- weather file reference and checksum;
- EnergyPlus command manifest;
- stdout;
- stderr;
- `eplusout.err`;
- `eplusout.sql`;
- `eplusout.csv`;
- `.eso` when retained;
- HTML tables/report when generated;
- sizing outputs;
- parsed summary JSON;
- timeseries artifacts;
- benchmark result JSON;
- comparison result JSON;
- complete run manifest.

The worker must record:

- EnergyPlus version;
- container image digest or executable checksum;
- operating system/runtime identity;
- command arguments;
- start/end times;
- exit code;
- severe and fatal counts;
- model checksum;
- weather checksum;
- scenario checksum;
- parser version.

---

## 14. Autosizing workflow

For incomplete buildings:

1. Validate geometry, loads, schedules, constructions, weather, and HVAC topology.
2. Run EnergyPlus sizing.
3. Parse autosized capacities and flows.
4. Store autosized values as provenance `AUTOSIZED`.
5. Create an immutable autosized baseline derivative.
6. Permit scenario multipliers against autosized values.
7. Report unmet hours and sizing warnings.

An intentionally undersized scenario must never overwrite autosized baseline values.

---

## 15. Calibration workflow

Calibration is optional and explicit.

Supported target levels may include:

- annual utility totals;
- monthly electricity;
- monthly gas;
- interval whole-building power;
- BAS equipment runtime;
- BAS temperatures and setpoints;
- seasonal peaks.

Every calibration run records:

- target data;
- included and excluded periods;
- weather alignment;
- adjustable parameters;
- parameter bounds;
- objective function;
- optimizer or agent method;
- number of evaluations;
- best metrics;
- validation period;
- final assumptions.

The UI must distinguish:

- uncalibrated estimated model;
- partially calibrated model;
- calibrated model;
- validated model.

---

## 16. HVAC benchmark contract

The independent benchmark library is run from the same scenario inputs where meaningful.

Possible outputs:

- peak cooling load;
- peak heating load;
- fan power;
- pump power;
- ventilation load;
- economizer opportunity;
- runtime estimate;
- annualized energy estimate;
- equipment efficiency estimate;
- schedule-hours estimate.

Comparison output:

```json
{
  "schema_version": "vibe21.comparison.v1",
  "metric": "peak_cooling_load",
  "units": "kW",
  "energyplus_value": 512.4,
  "benchmark_value": 486.1,
  "difference": 26.3,
  "difference_percent": 5.41,
  "assumption_mismatches": [
    "EnergyPlus includes latent load; benchmark uses simplified latent factor."
  ]
}
```

Difference is information, not automatically an error.

---

## 17. Vibe 19 analytics integration

The Vibe 19 adapter must expose structured data rather than screenshots.

Minimum integration outputs:

- package validation report;
- equipment inventory;
- equipment types;
- logical role mappings;
- point inventory;
- occupancy schedule;
- effective weather series;
- rule execution results;
- skipped/not-applicable reasons;
- fault intervals;
- runtime analytics;
- comfort analytics;
- RCx findings;
- engineering notes;
- source artifact references.

Unity may visualize a fault only when it can identify:

- rule ID;
- equipment ID;
- time range or aggregate period;
- severity;
- status;
- source result record.

---

## 18. Unity WebGL contract

### 18.1 Serving

The Unity build must be served with correct MIME and content-encoding headers for:

- loader JavaScript;
- framework JavaScript;
- `.wasm`;
- `.data`;
- compressed variants;
- streaming assets.

Production should use a reverse proxy or static server optimized for Unity WebGL assets.

### 18.2 Communication

Unity uses HTTPS requests for:

- project/building data;
- equipment detail;
- scenarios;
- job submission;
- job status;
- result summaries;
- spatial timeseries frames.

The web shell may communicate with Unity through:

- `unityInstance.SendMessage(...)`;
- a Unity `.jslib` bridge;
- browser `postMessage`;
- or a documented equivalent.

### 18.3 Unity object binding

Every visual object that represents engineering data carries a binding key.

Example:

```json
{
  "schema_version": "vibe21.unity_binding.v1",
  "unity_object_key": "Building100/Floor2/VAV_7",
  "entity_type": "equipment",
  "entity_id": "equip_vav_7",
  "default_visualization": "comfort_status"
}
```

### 18.4 Initial visual modes

- equipment type;
- operational status;
- fault severity;
- zone temperature;
- zone comfort;
- unmet hours;
- annual energy intensity;
- peak load;
- airflow;
- supply-air temperature;
- baseline-versus-scenario delta;
- data quality/confidence.

### 18.5 Time playback

Annual results are reduced into requested frames or timeseries.

The client must not download every raw simulation column by default.

Time playback requests specify:

- result ID;
- metric;
- entity IDs;
- period;
- aggregation;
- maximum points.

---

## 19. Browser shell

Recommended layout:

```text
┌──────────────────────────────────────────────────────────────┐
│ Project / building / baseline / scenario / job state         │
├───────────────┬────────────────────────────┬─────────────────┤
│ Inputs        │ Unity WebGL digital twin   │ Results         │
│               │                            │                 │
│ schedules     │ building / systems / zones │ KPIs            │
│ capacities    │ equipment selection        │ Plotly charts   │
│ ventilation   │ spatial result coloring    │ diagnostics     │
│ setpoints     │ time playback              │ assumptions     │
│ weather       │                            │ artifacts       │
│ [Run]         │                            │ [Export]        │
└───────────────┴────────────────────────────┴─────────────────┘
```

Ordinary web controls are preferred for dense engineering forms, tables, and Plotly charts. Unity is preferred for spatial selection and visualization.

---

## 20. Streamlit prototype mode

A Streamlit prototype may:

- call the API;
- embed Unity in an iframe or custom component;
- create scenarios;
- submit jobs;
- poll job state;
- render Plotly results;
- display reports and artifacts.

For a simple iframe, Unity and Streamlit communicate through the shared API.

For direct two-way interaction, implement a custom Streamlit component or a documented browser bridge.

Core backend behavior must remain testable without launching Streamlit.

---

## 21. Agentic AI behavior

Agents may:

- inspect project state;
- validate packages;
- propose mappings;
- propose assumptions;
- explain uncertainty;
- create scenario drafts;
- submit approved or policy-allowed jobs;
- inspect EnergyPlus diagnostics;
- revise a failed scenario;
- compare results;
- generate engineering narratives.

Agents must not:

- fabricate missing measurements;
- hide severe/fatal errors;
- silently broaden parameter bounds;
- overwrite a baseline;
- claim savings without a baseline and comparison method;
- claim calibration without metrics;
- issue BAS control commands;
- expose secrets;
- submit unlimited simulations;
- or delete source artifacts.

Every agent action that changes project state is auditable.

---

## 22. Security requirements

- Validate and cap uploads.
- Scan archive entries before extraction.
- Use per-run isolated directories.
- Do not permit user-selected executable paths.
- Allowlist model patches.
- Set request size limits.
- Apply authentication before multi-user deployment.
- Apply project-level authorization.
- Rate-limit simulation submission.
- Avoid serving arbitrary filesystem paths.
- Use signed or authorized artifact downloads.
- Set a Content Security Policy compatible with Unity.
- Protect against CSRF where cookie authentication is used.
- Keep secrets server-side.
- Record audit events.

---

## 23. Observability

Minimum structured events:

- package accepted/rejected;
- model created;
- scenario created;
- job submitted;
- job leased;
- stage changed;
- EnergyPlus started/completed;
- parser completed;
- benchmark completed;
- warning/error recorded;
- report created;
- artifact downloaded;
- cancellation requested/completed.

Metrics may include:

- queued jobs;
- running jobs;
- job duration by stage;
- success/failure counts;
- severe/fatal counts;
- worker availability;
- artifact size;
- API latency;
- cache hit rate.

---

## 24. Testing strategy

### 24.1 Contract tests

- scenario schema;
- job schema;
- result schema;
- Unity binding schema;
- package adapter schema;
- artifact manifest schema.

### 24.2 Unit tests

- patch validation;
- unit conversion;
- identity mapping;
- provenance rules;
- status transitions;
- EnergyPlus diagnostic parsing;
- comparison calculations.

### 24.3 Integration tests

- submit job through API;
- worker executes a tiny deterministic model;
- artifacts persist;
- result parser completes;
- Unity binding payload resolves;
- Streamlit or browser client can poll state.

### 24.4 Golden tests

Maintain at least:

- a tiny one-zone EnergyPlus model;
- a small packaged Vibe 19 demonstration building;
- a known autosizing scenario;
- a known undersized scenario;
- a no-outdoor-air scenario;
- a failed EnergyPlus model;
- a benchmark comparison fixture.

### 24.5 End-to-end acceptance

A browser test must:

1. open the app;
2. select a project;
3. create a scenario;
4. submit it;
5. observe state transitions;
6. receive a completed result;
7. display a Unity-bound metric;
8. display a Plotly comparison;
9. download a run manifest.

---

## 25. Initial milestone plan

### Milestone 0 — specification

- create Vibe 21 directory;
- freeze initial schemas;
- define sample requests/responses;
- identify Vibe 19 and Vibe 20 adapter boundaries.

### Milestone 1 — deterministic local backend

- project/scenario/job records;
- local single worker;
- one EnergyPlus fixture;
- durable artifacts;
- result manifest.

### Milestone 2 — web/API proof

- FastAPI application;
- Pydantic v2 request and response models;
- generated and tested OpenAPI contract;
- job polling;
- plain HTML controls;
- Plotly result;
- same-origin static serving.

### Milestone 3 — Unity proof

- Unity WebGL served;
- one building scene;
- canonical equipment bindings;
- scenario submission;
- completed-result coloring;
- selected-equipment details.

### Milestone 4 — Vibe 19 bridge

- load a building package;
- expose equipment and analytics;
- link findings to Unity objects.

### Milestone 5 — Vibe 20 bridge

- baseline model;
- autosizing;
- scenario patching;
- HVAC benchmark;
- baseline/scenario comparison.

### Milestone 6 — analyst workbench

- optional Streamlit shell;
- assumptions review;
- calibration inputs;
- report generation;
- session/project export.

### Milestone 7 — deployable worker system

- Redis-backed queue;
- retries;
- cancellation;
- multiple workers;
- authentication;
- retention policy;
- production hardening.

---

## 26. Definition of done for the first usable release

The release is usable when:

- one web address serves the application and Unity WebGL;
- a valid project can be created from a demonstration package;
- equipment IDs are consistent across analytics, EnergyPlus bindings, API responses, and Unity;
- a baseline model can be selected;
- a user can create an undersized/no-OA/extended-hours scenario;
- the FastAPI API validates the request with Pydantic and returns a job ID without blocking;
- a worker completes the simulation;
- diagnostics and artifacts are retained;
- results include energy, peak, unmet hours, and comfort;
- the independent HVAC benchmark is displayed;
- Unity colors at least zones or equipment from result data;
- Plotly displays a baseline/scenario comparison;
- all assumptions and provenance are downloadable;
- the run can be reproduced from exported manifests;
- automated tests prove the workflow.

---

## 27. Open design decisions

Agents must document a recommendation before implementation for:

- local queue abstraction;
- Redis worker library;
- SQLite versus PostgreSQL transition;
- filesystem versus object storage;
- IDF versus epJSON primary patch format;
- Unity scene source and object naming;
- web shell framework;
- Unity-to-JavaScript bridge;
- timeseries storage format;
- project export format;
- authentication model;
- calibration optimization strategy.

FastAPI, Pydantic v2, Uvicorn, and OpenAPI are fixed decisions rather than prototype defaults. Remaining choices may use prototype defaults, but persisted schemas must avoid unnecessary infrastructure vendor lock-in.

---

## 28. Guiding principle

A Vibe 21 digital twin is trustworthy only when a user can answer:

- What came from the BAS?
- What came from weather?
- What was measured?
- What was inferred?
- What was autosized?
- What did the user change?
- What did EnergyPlus calculate?
- What did the independent benchmark calculate?
- Why do they differ?
- Which Unity object represents which engineering entity?
- Can this exact result be reproduced?

If those questions cannot be answered from the project artifacts, the feature is incomplete.
