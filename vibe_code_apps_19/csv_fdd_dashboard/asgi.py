"""
ASGI entry for production servers (Uvicorn / Gunicorn+UvicornWorker).

  uvicorn asgi:app --host 0.0.0.0 --port 5000
  gunicorn -k uvicorn.workers.UvicornWorker --timeout 300 --bind 0.0.0.0:5000 asgi:app
"""

import os

os.environ.setdefault("DASHBOARD_MODE", os.environ.get("DASHBOARD_MODE", "full"))
os.environ.setdefault("ANALYST_ENABLED", "1")

from app import application as app  # noqa: E402, F401
