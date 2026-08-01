"""Flat WSGI entry for PythonAnywhere — same pattern as CannonPhysicsSim.

Extract the turnkey zip into the app root (e.g. `/home/bensApi` or `mysite`).
Layout: `flask_app.py`, `twin_api/`, `webgl/`, `ml/`, `requirements.txt`.

WSGI:

```python
import sys
project_home = "/home/bensApi"  # or /home/bensApi/mysite
if project_home not in sys.path:
    sys.path = [project_home] + sys.path
from flask_app import app as application
```
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
WEBGL_DIR = BASE_DIR / "webgl"

# Cannon layout: always webgl/ next to this file (before importing twin_api)
os.environ["VIBE21_WEBGL_DIR"] = str(WEBGL_DIR)

# Models live under twin_api/models in the turnkey zip
_models = BASE_DIR / "twin_api" / "models"
for _stem in ("demand_hourly_v2", "demand_hourly_v1"):
    _art = _models / f"{_stem}.joblib"
    _card = _models / f"{_stem}_model_card.json"
    if _art.is_file() and _card.is_file():
        os.environ.setdefault("VIBE21_MODEL_ARTIFACT", str(_art))
        os.environ.setdefault("VIBE21_MODEL_CARD", str(_card))
        break

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from twin_api.app import create_app  # noqa: E402

app = create_app()
application = app

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False)
