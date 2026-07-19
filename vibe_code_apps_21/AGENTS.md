# Agent prompt — Vibe 21 OpenFDD EnergyPlus Unity Digital Twin

## Mission

Build Vibe Code App 21 as the final integrated successor to Vibe Apps 19 and 20:

- preserve the Vibe 19 Open-FDD data package, mapping, schedule, weather, FDD, RCx, and reporting concepts;
- preserve the Vibe 20 EnergyPlus, autosizing, calibration, scenario, ECM, and HVAC benchmark concepts;
- add a browser-hosted Unity WebGL digital twin;
- expose stable APIs so Unity, a web shell, Streamlit, CLI agents, and automated tests use the same backend contracts.

Before implementation, read:

1. `README.md`
2. `vibe21_agent_spec/SPEC.md`
3. `../vibe_code_apps_19/AGENTS.md`
4. `../vibe_code_apps_19/vibe19_agent_spec/`
5. `../vibe_code_apps_20/AGENTS.md`
6. `../vibe_code_apps_20/vibe20_agent_spec/`

Vibe 19 and Vibe 20 are source systems and behavioral references. Do not casually copy their entire trees into Vibe 21.


## Required backend stack

The backend choice is closed:

- **FastAPI** is the only HTTP API framework.
- **Pydantic v2** models are the canonical validation and serialization layer.
- **Uvicorn** is the required local/development ASGI server.
- FastAPI-generated **OpenAPI 3.x** is the canonical API description used by browser, Unity, Streamlit, CLI, and generated clients.
- Framework-neutral domain services may sit behind FastAPI, but no parallel Flask, Django, Sanic, Litestar, or Streamlit-owned backend may be introduced.
- Streamlit, when present, is only an API client and analyst UI.
- Redis remains optional and must sit behind a queue abstraction.

## Product outcome

A user opens one web address and can:

- load an Open-FDD building package;
- inspect BAS-derived equipment, data quality, schedules, faults, and RCx findings;
- configure an EnergyPlus baseline and scenarios;
- click a Unity building, zone, AHU, VAV, plant item, or meter and inspect its linked engineering data;
- change approved scenario inputs with sliders and forms;
- submit a simulation without blocking the browser request;
- watch deterministic job state;
- compare baseline, degraded, and ECM scenarios;
- visualize comfort, energy, faults, runtime, and simulation outputs in 3D and conventional charts;
- export all inputs, outputs, logs, reports, and provenance needed to reproduce the run.

## Hard rules

1. **Specification first.** Keep `vibe21_agent_spec/SPEC.md` current before material architecture changes.
2. **No hidden coupling to Streamlit.** Domain logic, API models, jobs, simulation runners, result parsers, and storage must be UI-independent.
3. **No EnergyPlus execution inside a long-lived HTTP request.** Simulation submission returns a job identifier; a worker performs the run.
4. **No invented building facts.** Estimated values must be labeled with source, confidence, assumption, and method.
5. **Autosized, inferred, measured, defaulted, and user-entered values are distinct provenance classes.**
6. **Never overwrite the immutable baseline model.** Every scenario is a patch or derived model with a manifest.
7. **Never mutate the uploaded BAS source package.** Derived mappings and session settings are stored separately.
8. **Unity is a client, not the source of truth.** Unity object state must be reconstructed from backend records.
9. **Do not store critical state only in browser memory, Unity PlayerPrefs, Streamlit session state, or Redis.**
10. **Redis is optional infrastructure.** The queue abstraction must permit a simple local worker for development and Redis-backed workers for deployment.
11. **Durable records belong in a database or filesystem/object storage.** Redis may coordinate jobs, cache data, and publish transient progress.
12. **Use same-origin routing by default.** Serve the web shell/Unity and reverse-proxy `/api/` and `/results/` under one origin.
13. **All external paths are untrusted.** Prevent path traversal, zip-slip, symlink escape, decompression bombs, unsafe uploads, and arbitrary command arguments.
14. **No shell interpolation for EnergyPlus execution.** Use validated argument arrays and isolated per-run directories.
15. **Every job is idempotent or explicitly non-idempotent.** Repeated submissions must not silently corrupt or overwrite prior results.
16. **Model and schema versions are mandatory.** API, scenario, package, Unity binding, and result schemas carry explicit versions.
17. **Stable equipment identity is mandatory.** Do not link Unity objects to display names alone.
18. **Missing data produces explicit status.** Use skipped, unavailable, not applicable, estimated, failed, or partial states rather than fabricated values.
19. **Vibe 19 rule semantics remain testable.** Do not silently change fault definitions while integrating them.
20. **Vibe 20 benchmark semantics remain independent from EnergyPlus.** Do not tune the benchmark merely to force agreement.
21. **Simulation failures are first-class results.** Preserve `eplusout.err`, exit status, severe/fatal diagnostics, logs, and partial artifacts.
22. **No fake progress percentages.** Progress is stage-based unless EnergyPlus provides defensible progress information.
23. **Annual simulations and interactive playback are separate concerns.** Do not imply real-time co-simulation unless it is actually implemented.
24. **Batch simulation comes before live co-simulation.**
25. **Do not expose arbitrary EnergyPlus object editing to untrusted users.** Scenario fields use an allowlisted patch model.
26. **No secrets in git, Unity builds, browser JavaScript, reports, logs, or downloadable manifests.**
27. **Tests and reproducibility evidence are required before declaring a feature complete.**
28. **Do not rewrite or delete Vibe Apps 19 or 20 as part of Vibe 21 work.**
29. **Do not claim model calibration without reporting the target data, objective function, period, exclusions, and achieved metrics.**
30. **Human-readable engineering warnings must accompany technically successful but questionable simulations.**
31. **FastAPI is mandatory.** Reject proposals that replace it or add a second backend web framework.
32. **Pydantic v2 schemas are authoritative.** Do not maintain separate handwritten request schemas that can drift from runtime validation.
33. **OpenAPI compatibility is tested.** Breaking contract changes require an explicit API/schema version change.

## Required conceptual boundaries

Keep these concerns separable:

- package ingestion and validation;
- canonical building/equipment/point identity;
- Vibe 19 analytics;
- weather resolution;
- EnergyPlus model inventory;
- assumption and provenance registry;
- scenario definitions;
- model patching;
- job orchestration;
- EnergyPlus execution;
- result parsing;
- HVAC benchmark calculations;
- comparison and calibration;
- report generation;
- Unity binding and visualization;
- authentication and authorization;
- storage and retention.

## Preferred implementation order

1. Freeze schemas and sample manifests.
2. Build a deterministic local, single-worker simulation path.
3. Add durable job and artifact records.
4. Add API endpoints and generated API documentation.
5. Add a plain browser proof of concept.
6. Add Unity WebGL object binding and result coloring.
7. Add Vibe 19 package/analytics bridge.
8. Add Vibe 20 model/benchmark bridge.
9. Add optional Streamlit analyst shell.
10. Add Redis-backed queue and multiple workers only after local behavior is proven.
11. Add calibration loops and agent workflows after reproducibility is proven.
12. Consider live co-simulation only after batch workflows are stable.

## Completion discipline

For each implementation session, record:

- scope attempted;
- files changed;
- schemas changed;
- commands run;
- tests and outcomes;
- sample job identifiers;
- generated artifacts;
- known limitations;
- follow-up tasks;
- whether Vibe 19 or Vibe 20 behavior changed.

Never report “done” using screenshots alone. Provide machine-verifiable evidence.
