#!/usr/bin/env python
"""Backward-compatible alias — use eplus_fetch_open_meteo_epw.py."""
from __future__ import annotations

import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))
sys.path.insert(0, str(_APP / "scripts"))

from eplus_fetch_open_meteo_epw import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
