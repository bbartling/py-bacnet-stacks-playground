# PythonAnywhere Deployment Contract — Vibe 21

## Goal

Produce one lightweight WSGI web application that a human can upload/unzip on PythonAnywhere and configure through the Web tab.

The deployment serves:

- Flask JSON inference endpoints (`/api/v1/health`, `/api/v1/predict/demand_hourly`);
- compiled Unity WebGL assets (primary demo path);
- optional compiled React assets;
- model metadata and safe demonstration data.

It does **not** execute EnergyPlus or train ML models.

**Working mirror checklist:** [`../pythonanywhere_mirror/README.md`](../pythonanywhere_mirror/README.md)  
Align with CannonPhysicsSim: `C:\Users\ben\Documents\CannonPhysicsSim\pythonanywhere_flask` (flat `flask_app.py`, `webgl/`, static maps for `/Build/` + `/TemplateData/`).

Live package for local + PA: `vibe_code_apps_21/flask_app/` (`create_app()` also serves `flask_app/webgl/` at `/` when present).

**Turnkey pack:** `python tools/pack_pa_bundle.py` → `dist/vibe21_pa_bundle.zip`.  
Joblib lives under **`flask_app/models/`** (not a separate top-level `models/` folder) so unzip + reload works without path surgery.

## PythonAnywhere Files upload cap (100 MiB)

The **Files page orange upload button** (and other HTTP uploads) hard-cap at **100 MiB**. This is a platform limit — it cannot be raised.

- Keep the turnkey zip ≤100 MiB (API + joblib ~13 MiB + notebook HTML; add WebGL only if the zip still fits).
- If over 100 MiB: **SFTP/SCP** (paid) or `split`/`cat` chunks — see [PA uploading help](https://help.pythonanywhere.com/pages/UploadingAndDownloadingFiles/).
- `pack_pa_bundle.py` **exits non-zero** when the zip exceeds 100 MiB unless `--force`.

---

## Expected deployment bundle

```text
vibe21_pa_bundle.zip   # ≤100 MiB for Files upload
├── README_PA.md
├── flask_app/
│   ├── app.py, model_loader.py, predict.py, requirements.txt
│   ├── models/demand_hourly_v1.joblib (+ card, tuning)
│   ├── static/notebooks/*.html
│   └── webgl/                 # optional Unity export
├── ml/                        # feature_compile + artifact_paths (+ tune helpers)
├── notebooks/*.ipynb
└── pythonanywhere_mirror/flask_app.py
```

---

## WSGI rule

The PythonAnywhere WSGI file imports the Flask application object. The deployed app must not depend on calling `app.run()`.

Local: `python -m flask_app` (:5050).

---

## Static asset strategy

Preferred **demo** mapping (CannonPhysicsSim style):

- `/` → `webgl/index.html` (Flask `send_from_directory` or PA static);
- `/Build/` → `webgl/Build`;
- `/TemplateData/` → `webgl/TemplateData`.

Flask owns `/api/v1/`. Unity WebGL `DemandApiClient` uses **same-origin** base URL.

Optional React shell may live under `/static/react/` and iframe `/` or `/unity/`.

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
