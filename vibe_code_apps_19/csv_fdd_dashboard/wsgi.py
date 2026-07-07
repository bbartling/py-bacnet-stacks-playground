"""
PythonAnywhere WSGI entry point.

In the PythonAnywhere Web tab set:
  Source code:  /home/YOURUSERNAME/building100_dashboard
  WSGI file:    /var/www/YOURUSERNAME_pythonanywhere_com_wsgi.py

Replace the default file contents with:

    import sys
    path = '/home/YOURUSERNAME/building100_dashboard'
    if path not in sys.path:
        sys.path.insert(0, path)
    import os
    os.environ['DASHBOARD_MODE'] = 'deploy'
    os.environ['ANALYST_ENABLED'] = '1'   # set to 0 for view-only (no note editing)
    from app import application
"""

import os

os.environ.setdefault("DASHBOARD_MODE", "deploy")
os.environ.setdefault("ANALYST_ENABLED", "1")

from app import application  # noqa: E402, F401
