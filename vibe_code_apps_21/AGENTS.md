# AGENTS.md — Vibe 21 Demand-Management Digital Twin

## Mission

Fine-tune Vibe 21 as a **demand-management digital twin** for Unity:

1. consume the G14 Twin IDF + AMY (`assets/twin_b100_ops11/`);
2. run offline EnergyPlus **hourly** DR / load-shift farms (EnergyPlus-MCP as helper);
3. build synthetic datasets whose target is **hourly facility kW under OA + HVAC actions**;
4. train lightweight scikit-learn demand models offline;
5. serve Flask inference + React charts + Unity Editor/WebGL massing/controls;
6. keep Excel product path on **open-fdd PyPI `ECMJob`** (WattLab workbook is oracle only).

**Read first:** `vibe21_agent_spec/DEMAND_MANAGEMENT_TWIN.md`, then
`UNITY_MCP_WORKFLOW.md`, then `ML_SYNTHETIC_DATA_GAPS.md`, then
`skills/wattlab-eplus-demand-hourly/SKILL.md`.

Broader physics-ML language in older `SPEC.md` / `ML_ARCHITECTURE.md` is
**legacy context** — do not expand scope beyond DM without an explicit revise.

## Closed technology decisions for the first PythonAnywhere demo

- **Flask** is the HTTP framework.
- The public deployment target is traditional **WSGI** on PythonAnywhere.
- **scikit-learn** is the primary ML framework.
- Trusted models are persisted with **joblib** along with exact dependency/version metadata.
- **React** is the conventional web shell.
- **Plotly** is preferred for engineering charts.
- **Unity Editor + WebGL** is the spatial twin (`unity/liberty_100/`); WebGL is
  the eventual embed path. Editor work is driven via **Unity MCP** with
  **`manage_scene` save after every milestone** (UI lockups lose unsaved work).
- Local Flask inference default port **`:5050`** (`flask_app/`). Unity calls
  `POST /api/v1/predict/demand_hourly` — never loads joblib inside the Editor.
- **Parquet** is the canonical ML training dataset format.
- **JSON** is the canonical web/API interchange format.
- Training and EnergyPlus simulation happen **offline**, not inside the public Flask app.

Do not re-introduce FastAPI into the first Vibe 21 PythonAnywhere implementation unless the specification is intentionally revised. The previous Vibe 21 scaffold locked FastAPI because it assumed server-side EnergyPlus jobs; that assumption is replaced by offline physics/training plus lightweight online inference.

## Hard rules

1. **Vibe 21 is inference-first in deployment.** No EnergyPlus execution on PythonAnywhere for the first release.
2. **No training from a public HTTP request.** Training is a local/CI/offline workflow.
3. **No arbitrary pickle/joblib uploads.** `joblib`/pickle artifacts can execute code when deserialized; only repository-approved or otherwise trusted artifacts with matching hashes may be loaded.
4. **No invented building facts.** Preserve provenance: measured, mapped, inferred, autosized, calibrated, simulated, derived, unknown.
5. **Synthetic is not measured.** Every ML training row carries source/scenario provenance.
6. **Calibration claims follow Vibe 20 evidence.** An uncalibrated EnergyPlus prototype may create conceptual synthetic data, but its resulting ML model must be labeled conceptual.
7. **Do not random-split adjacent timesteps.** Time-correlated and same-simulation rows must not leak across train/validation/test.
8. **Split by simulation/scenario group first.** Hold out complete `simulation_id` groups; for real BAS validation also hold out contiguous time windows.
9. **Never use future information as a feature.** No daily peak computed using future hours, no future rolling window, no target-derived feature leakage.
10. **Runtime features must be reproducible.** Rolling, lag, slope, and occupancy features are created by one versioned feature compiler used by training and inference.
11. **A single JSON row cannot recreate historical features.** APIs requiring lagged/rolling features must receive a sufficient lookback window or reference persisted recent state.
12. **Demand and energy remain unit-consistent.** kW is power; kWh is energy. For fixed intervals derive kWh from average kW when that is the intended physical relationship.
13. **Do not force every target into one model.** Separate target models are the default. Multi-output modeling is an experiment that must beat or justify itself against separate-model baselines.
14. **FDD classification is separate from energy/demand regression.** It may share feature generation, not labels or validation logic.
15. **Scenario surrogate and operational twin are separate model families.** Do not mix scenario-level annual targets with timestep-level rows in one estimator.
16. **Use a model registry.** Every model has model ID, type, target(s), feature schema, training dataset hash, code version, sklearn version, metrics, validation split, status, and artifact hash.
17. **No model is `APPROVED` because training score looks good.** Holdout performance and sanity checks are mandatory.
18. **Compare to trivial baselines.** At minimum include persistence/previous-value where relevant and simple linear/Ridge baselines.
19. **Real BAS validation is preferred.** Synthetic holdout success alone does not prove real-building accuracy.
20. **Prediction responses expose provenance.** Return model ID/version, timestamp, units, feature coverage, warnings, and confidence/uncertainty status.
21. **Out-of-domain detection is mandatory.** Warn when live/scenario inputs fall materially outside the training envelope.
22. **Unity is a client, not the source of truth.** Unity object names never replace stable entity IDs.
23. **React is for dense engineering controls; Unity is for spatial interaction.** Do not make Unity the only way to inspect numbers or provenance.
24. **Same-origin by default.** React, Unity and `/api/v1/` use one deployment origin unless explicitly changed.
25. **The Unity build is generated externally.** Do not pretend the Python agent created/edited Unity scenes unless it actually used the Unity tooling.
26. **The final deployment zip contains generated web artifacts, not a Unity Editor project.** Source Unity Editor project lives under `vibe_code_apps_21/unity/<ProjectName>/` (never the package root). Twin JSON/IDF stay in `assets/`.
27. **No BAS commanding.** Vibe 21 is read-only prediction/visualization for the first release.
28. **No secrets in React, Unity, model cards, JSON manifests, logs, or git.**
29. **Do not expose raw customer historian data in a public demo bundle.** Use anonymized/demo data or precomputed safe state.
30. **Keep model files small enough for the chosen hosting tier.** Benchmark memory/load time before approving large forests.
31. **Load approved models once at process startup/lazy singleton, not on every prediction request.**
32. **Prediction latency is measured.** Report p50/p95 on representative requests.
33. **Never claim causal savings from ML prediction alone.** ECM savings remain rooted in a documented baseline/scenario method and Vibe 20 evidence.
34. **EnergyPlus remains the physics reference, not an oracle.** Synthetic data inherits model assumptions and calibration error.
35. **Keep independent Vibe 20 engineering benchmark comparisons.** Do not train the ML model to erase disagreements without engineering review.
36. **Schema versions are mandatory.** Feature, target, model-bundle, prediction, scenario, Unity-binding, and deploy manifests are versioned.
37. **Tests are mandatory.** Unit, contract, leakage, model-loading, prediction, React route, Unity asset, and deploy-bundle smoke tests are required.
38. **Do not report done from screenshots.** Provide test output and reproducible artifact hashes.

## Model strategy

### Operational demand model

Default champion search:

- Ridge baseline;
- `HistGradientBoostingRegressor`;
- `RandomForestRegressor`;
- `ExtraTreesRegressor`.

Primary target: average whole-building electric demand `building_kw` for the modeled interval.

Optional horizon-specific models:

- `building_kw_now`;
- `building_kw_t_plus_15m`;
- `building_kw_t_plus_60m`.

For 15-minute average demand, derive interval energy:

```text
interval_kwh = predicted_building_kw * 0.25
```

Do not separately predict the same interval kWh unless there is a documented reason and a consistency test.

### Scenario surrogate model

Separate scenario-level models or a carefully validated multi-output experiment predict:

- annual electricity kWh;
- monthly electricity kWh;
- peak demand kW;
- natural gas therm/year;
- unmet hours;
- comfort violation hours;
- selected end-use totals.

### Multi-output experiments

Allowed:

- estimators with native multi-output support such as `RandomForestRegressor`;
- `MultiOutputRegressor(base_estimator)` when the base estimator is single-target;
- `RegressorChain` only when target-to-target dependence is intentionally modeled and leakage is controlled.

Default production posture remains **one well-defined model per engineering target/horizon**, sharing one feature compiler.

## Preferred implementation order

1. Freeze Vibe 19 → Vibe 21 and Vibe 20 → Vibe 21 handoff manifests.
2. Define canonical feature and target schemas.
3. Implement the versioned feature compiler with leakage tests.
4. Build a tiny deterministic EnergyPlus synthetic dataset fixture.
5. Build the offline simulation-farm runner and dataset manifest.
6. Train baseline and candidate demand models.
7. Train scenario surrogate models.
8. Implement grouped/blocked validation and model cards.
9. Export one approved model bundle.
10. Build Flask inference endpoints and model registry loader.
11. Build React engineering shell against fixture API responses.
12. Editor twin via Unity MCP: IDF massing + free-fly/drone + DR UI → Flask.
13. Add Unity WebGL external build handoff and object binding.
14. Produce a PythonAnywhere deploy bundle and smoke test it locally under WSGI-like conditions.
15. Only then scale the simulation farm or add optional FDD/virtual-sensor models.

## Unity MCP save discipline

When editing `unity/liberty_100` via MCP, call `manage_scene(action="save")`
after each milestone (geometry, camera/site, DR UI, sensors/AHU, end of session).
Editor UI freezes often; MCP save still works and prevents full restarts.

## Completion discipline

Every implementation session records:

- scope;
- files changed;
- dataset/schema versions;
- simulations created or consumed;
- feature changes;
- model candidates trained;
- validation split definition;
- metrics;
- artifact hashes;
- tests run and outcomes;
- deployment smoke results;
- known limitations;
- whether any Vibe 19/20 behavior changed.
