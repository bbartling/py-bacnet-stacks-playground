"""
ASGI entry for production servers (Uvicorn / Gunicorn+UvicornWorker).

  cd fdd_app
  uvicorn asgi:app --host 0.0.0.0 --port 5000
  gunicorn -k uvicorn.workers.UvicornWorker --timeout 300 --bind 0.0.0.0:5000 asgi:app
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("DASHBOARD_MODE", os.environ.get("DASHBOARD_MODE", "full"))
os.environ.setdefault("ANALYST_ENABLED", "1")

_FDD_APP = Path(__file__).resolve().parent
_BACKEND = _FDD_APP / "backend"
_SIDECAR = _FDD_APP / "sidecar"
_APP19 = _FDD_APP.parent
for _p in (_APP19, _BACKEND, _SIDECAR):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from app import application as app  # noqa: E402, F401
