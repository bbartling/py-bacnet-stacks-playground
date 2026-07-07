"""
WSGI entry for production servers (Gunicorn, uWSGI, etc.).

  gunicorn --bind 0.0.0.0:5000 --threads 4 --timeout 300 wsgi:application
"""

import os

os.environ.setdefault("DASHBOARD_MODE", os.environ.get("DASHBOARD_MODE", "full"))
os.environ.setdefault("ANALYST_ENABLED", "1")

from app import application  # noqa: E402, F401
