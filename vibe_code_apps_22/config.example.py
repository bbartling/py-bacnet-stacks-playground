"""Local prototype settings — copy to ``config.py`` (gitignored).

No secrets here. Env vars still override when set (CI / one-off scripts).
"""
from __future__ import annotations

from pathlib import Path

# Site pack root (must contain reports/). Edit in config.py for your machine.
SITE_ROOT: Path | None = Path(r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside")

# Optional convenience for local Streamlit (docs / muscle memory only).
STREAMLIT_PORT = 8766
