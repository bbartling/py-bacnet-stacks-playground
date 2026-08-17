"""Local prototype settings — copy to ``config.py`` (gitignored).

No secrets here. Env vars still override when set (CI / one-off scripts).
"""
from __future__ import annotations

from pathlib import Path

# Site pack root (must contain reports/). Set in gitignored config.py or SITE_ROOT.
SITE_ROOT: Path | None = None

# Optional convenience for local Streamlit (docs / muscle memory only).
STREAMLIT_PORT = 8766
