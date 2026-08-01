# PythonAnywhere mirror (Vibe21 DM Twin)

Keep this folder aligned with the CannonPhysicsSim PA pattern at
`C:\Users\ben\Documents\CannonPhysicsSim\pythonanywhere_flask` while the live
API lives in `vibe_code_apps_21/flask_app/`.

## Layout to upload

```
pythonanywhere_mirror/
  flask_app.py          # flat WSGI entry (create_app)
  requirements.txt
  webgl/                # Unity WebGL export (index.html + Build + TemplateData)
  models/               # optional joblib + model card (or set VIBE21_MODEL_*)
```

## WSGI (PythonAnywhere Web tab)

```python
import sys
path = "/home/YOURUSER/vibe21_dm_twin"
if path not in sys.path:
    sys.path.insert(0, path)
from flask_app import app as application  # flat module exports `app`
```

Or package form:

```python
from flask_app.app import create_app
application = create_app()
```

## Static files (Web → Static files)

| URL | Directory |
|-----|-----------|
| `/Build/` | `.../webgl/Build` |
| `/TemplateData/` | `.../webgl/TemplateData` |

API stays dynamic: `/api/v1/health`, `/api/v1/predict/demand_hourly`.

## Checklist

1. Export WebGL with **Decompression Fallback** (or uncompressed) into `webgl/`.
2. Copy trained joblib + card; set env if not under default model paths.
3. Reload PA web app; hit `/api/v1/health` then `/`.
4. Unity `DemandApiClient` uses page origin on WebGL (same-origin).

See also: `../vibe21_agent_spec/PYTHONANYWHERE_DEPLOYMENT.md`, `UNITY_WEBGL_HANDOFF.md`.
