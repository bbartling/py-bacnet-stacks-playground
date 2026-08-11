"""Put archived E+ helpers on sys.path. Live ml/ is gone."""
from __future__ import annotations

import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
_HELPERS = _APP / "archive" / "ml"
for _p in (_APP, _HELPERS):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
