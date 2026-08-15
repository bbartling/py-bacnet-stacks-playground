"""Put archived E+ helpers on sys.path. Live ml/ is gone."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Unit tests may use vendored rleplus helpers. Live campaigns must omit this.
os.environ.setdefault("VIBE22_ALLOW_VENDORED_FALLBACK", "1")

_APP = Path(__file__).resolve().parents[1]
_HELPERS = _APP / "archive" / "ml"
for _p in (_APP, _HELPERS):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
