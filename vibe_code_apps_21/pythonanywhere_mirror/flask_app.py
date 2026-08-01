"""Flat WSGI entry for PythonAnywhere — mirrors CannonPhysicsSim style.

Copy this file next to a `webgl/` folder on PA, or import create_app from the
package. Prefer running the package locally: `python -m flask_app`.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `from flask_app.app import create_app` when this file sits beside the package
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from flask_app.app import create_app  # noqa: E402

app = create_app()
application = app

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False)
