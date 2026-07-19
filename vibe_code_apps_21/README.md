# Vibe Code App 21 — OpenFDD EnergyPlus Digital Twin Studio

Vibe Code App 21 is the planned final integration of:

- **Vibe Code App 19** — BAS historian ingestion, equipment mapping, Open-FDD analytics, RCx findings, schedules, weather reconciliation, and engineering reports.
- **Vibe Code App 20 / OpenFDD WattLab** — EnergyPlus model creation, autosizing, scenario simulation, calibration, ECM comparison, and independent HVAC calculation benchmarks.
- **Unity WebGL** — an interactive browser-delivered 3D building digital twin used to select equipment, change scenario inputs, run simulations, and visualize results spatially.

This directory is intentionally **specification-only**. It contains no application code, generated Unity project, Docker files, Python package, or frontend implementation.

## Product vision

Create a browser-based engineering workbench where a user can:

1. Load or restore an Open-FDD building package.
2. Review BAS data quality, schedules, equipment mappings, faults, and RCx findings.
3. Generate or select an EnergyPlus baseline model.
4. autosize the HVAC system when design information is incomplete.
5. Create intentionally degraded scenarios, including undersized HVAC, unusual operating hours, missing outdoor-air ventilation, disabled economizers, and weather-extreme operation.
6. Queue and run EnergyPlus simulations through a backend service.
7. Compare EnergyPlus outputs against the local HVAC engineering calculation library from Vibe 20.
8. Display building, equipment, zones, fault state, comfort state, energy use, airflow, and simulation results in Unity WebGL.
9. Export reproducible scenario manifests, reports, charts, and model artifacts.

## Intended deployment shape

```text
Browser
├── Web application shell
│   ├── forms, sliders, tables, job state, Plotly charts
│   └── Unity WebGL canvas
│
└── HTTPS JSON API
    ├── building/package service
    ├── Open-FDD analytics service
    ├── scenario/model service
    ├── simulation job service
    └── results/report service
         │
         ├── EnergyPlus worker container(s)
         ├── Vibe 20 HVAC benchmark library
         └── durable project/result storage
```

The backend is **FastAPI only**. Pydantic models define API request, response, configuration, and persisted manifest contracts; Uvicorn serves the ASGI application; and FastAPI's generated OpenAPI document is the canonical machine-readable client contract.

The persisted engineering domain remains framework-independent in meaning, but implementation agents must not introduce Flask, Django, Streamlit callbacks, or a second HTTP framework as an alternative backend.

## Streamlit position

Streamlit may be used as an **engineering prototype or analyst workbench**, especially for:

- package upload and mapping,
- fault and schedule tuning,
- model configuration,
- scenario comparison,
- Plotly charts,
- report export,
- and embedding the Unity WebGL viewer.

Streamlit is not required to be the final product shell. The core APIs, scenario schemas, job records, and result artifacts must remain usable by Unity, Streamlit, a conventional JavaScript frontend, CLI agents, and tests without importing Streamlit.

## Specification files

- [`AGENTS.md`](AGENTS.md) — top-level agent mission, boundaries, and delivery rules.
- [`vibe21_agent_spec/SPEC.md`](vibe21_agent_spec/SPEC.md) — product, architecture, data-contract, API, simulation, Unity, and acceptance specification.

## Status

**Planning scaffold only. No code has been implemented.**
