# PythonAnywhere Deployment Contract — Vibe 21

## Goal

Produce one lightweight WSGI web application that a human can upload/unzip on PythonAnywhere and configure through the Web tab.

The deployment serves:

- Flask JSON inference endpoints;
- compiled React assets;
- compiled Unity WebGL assets;
- model metadata and safe demonstration data.

It does **not** execute EnergyPlus or train ML models.

---

## Expected deployment bundle

```text
vibe21_deploy_bundle/
├── flask_app.py
├── requirements.txt
├── README_PYTHONANYWHERE.md
├── vibe21/
│   ├── api/
│   ├── domain/
│   ├── features/
│   ├── inference/
│   ├── model_registry/
│   └── schemas/
├── models/
│   └── ... approved joblib + manifests ...
├── manifests/
│   ├── deploy_manifest.json
│   └── unity_bindings.json
├── static/
│   ├── react/
│   │   ├── index.html
│   │   └── assets/...
│   └── unity/
│       ├── index.html
│       ├── Build/...
│       └── TemplateData/...
└── tests/
```

The implementation may adjust exact package names, but the build must remain relocatable under a PythonAnywhere home directory.

---

## WSGI rule

The PythonAnywhere WSGI file imports the Flask application object. The deployed app must not depend on calling `app.run()`.

Local development may use Flask's development server only behind an `if __name__ == "__main__"` guard or a CLI entrypoint.

---

## Static asset strategy

React and Unity are precompiled before deployment.

Preferred production mapping:

- `/static/react/` → compiled React assets;
- `/static/unity/` → compiled Unity WebGL assets.

Flask owns `/api/v1/`.

The root route `/` serves or redirects to the React application shell.

For an easy demo, the React SPA may include an iframe or embedded container that loads `/static/unity/index.html`, or Flask may expose a friendly `/unity/` route.

---

## Unity compression compatibility

Unity WebGL compressed builds normally need correct content-encoding headers when relying on native browser decompression.

Because simple hosting may not expose custom server header configuration, the first PythonAnywhere-compatible Unity build should use one of these validated strategies:

1. **Preferred demo strategy:** Unity WebGL compression with **Decompression Fallback enabled**; or
2. **Compatibility strategy:** compression disabled for the WebGL build if package size remains acceptable.

The Unity agent must smoke test the exact exported build through a simple static/Flask-compatible server before handing it to the human.

Do not assume Brotli/gzip native serving works merely because the files uploaded successfully.

---

## Runtime dependency posture

Keep the deployment requirements intentionally small.

Core likely dependencies:

```text
Flask
numpy
pandas
scikit-learn
joblib
```

Optional only when justified:

```text
pyarrow       # only if runtime Parquet reads are needed
pydantic      # optional schema layer; not mandatory if dataclasses/manual validation chosen
```

Avoid shipping EnergyPlus, Unity Editor, Docker, SHAP, Jupyter, training notebooks, or large synthetic datasets in the public deploy bundle.

---

## Model startup behavior

- Read `model_registry.json`.
- Validate schema version.
- Validate model checksums.
- Validate supported scikit-learn/runtime compatibility.
- Load approved models once, eagerly or through a process-local lazy cache.
- Fail closed if required models are missing or hashes mismatch.
- Expose model status through `/api/v1/models` and `/api/v1/health`.

---

## Minimal API surface

```text
GET  /api/v1/health
GET  /api/v1/twin/manifest
GET  /api/v1/building
GET  /api/v1/equipment
GET  /api/v1/unity-bindings
GET  /api/v1/models
POST /api/v1/predict/operational
POST /api/v1/predict/scenario
POST /api/v1/predict/virtual-sensor      # optional
POST /api/v1/predict/faults              # optional
```

The public demo does not need simulation job endpoints because EnergyPlus jobs are offline.

---

## Prediction request limits

- Cap JSON body size.
- Cap history rows.
- Validate interval/grid.
- Validate timestamps.
- Reject unsupported fields or explicitly ignore with warnings according to schema policy.
- Rate limit if the public demo receives abuse.
- Never accept filesystem paths or executable commands from clients.

---

## Deployment manifest

The final zip contains:

```json
{
  "schema_version": "vibe21.deploy_manifest.v1",
  "app_version": "0.1.0",
  "model_registry": "models/model_registry.json",
  "react_build": "static/react",
  "unity_build": "static/unity",
  "python_target": "declared-by-build",
  "generated_at": "ISO-8601",
  "source_commit": "git-sha",
  "checksums_file": "checksums.sha256"
}
```

---

## Human upload workflow

The implementation should eventually make deployment approximately:

1. AI/local build pipeline produces `vibe21_deploy_bundle.zip`.
2. Unity MCP/agent produces a verified WebGL build zip.
3. Build pipeline merges the Unity artifacts under `static/unity/` and updates checksums.
4. Human uploads the final zip to PythonAnywhere.
5. Human unzips into a home/project directory.
6. Human creates/activates a virtualenv and installs `requirements.txt`.
7. Human configures the Web tab WSGI file to import `flask_app.app` as `application`.
8. Human configures static mappings if used.
9. Human reloads the web app.
10. Human visits `/api/v1/health`, `/`, and the Unity route.

The generated `README_PYTHONANYWHERE.md` must contain exact paths/placeholders for the chosen account/project name without hardcoding a developer's local Windows paths.

---

## Acceptance smoke tests

Before the zip is declared deployable:

- Flask app imports under WSGI-style import without starting a dev server;
- `/api/v1/health` returns 200;
- one golden operational request returns kW and derived kWh;
- one golden scenario request returns annual kWh and peak kW;
- root React route loads;
- React can call same-origin API;
- Unity index loads;
- Unity can request the twin manifest;
- one Unity binding resolves to a canonical equipment/zone ID;
- no model training or EnergyPlus executable is present in the deployed runtime path;
- checksums verify.
