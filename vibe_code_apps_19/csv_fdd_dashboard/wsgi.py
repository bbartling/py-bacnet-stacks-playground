"""
Deprecated entry — the app is now ASGI (FastAPI). Use asgi.py instead:

  uvicorn asgi:app --host 0.0.0.0 --port 5000
  gunicorn -k uvicorn.workers.UvicornWorker --timeout 300 asgi:app

Kept for backwards-compatible imports; `application` is the FastAPI ASGI app.
"""

import os

os.environ.setdefault("DASHBOARD_MODE", os.environ.get("DASHBOARD_MODE", "full"))
os.environ.setdefault("ANALYST_ENABLED", "1")

from app import application  # noqa: E402, F401

app = application
