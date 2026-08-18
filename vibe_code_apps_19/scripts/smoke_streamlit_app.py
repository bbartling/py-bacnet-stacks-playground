"""Programmatic Streamlit smoke check — catch ImportError / script exceptions early.

Usage (from vibe_code_apps_19):
  py -3.14 scripts/smoke_streamlit_app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from app.fdd_runtime import make_session_config  # noqa: F401
    from app.rcx_plots import rcx_preset_coverage  # noqa: F401

    assert callable(rcx_preset_coverage)
    assert callable(make_session_config)

    os.environ.setdefault("VIBE19_BROWSER_AUTOLOAD", "0")

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=180)
    at.run()
    if at.exception:
        print("FAIL: AppTest exceptions:")
        for exc in at.exception:
            print(f"  - {exc}")
        return 1
    frames = {}
    try:
        frames = at.session_state.get("equipment_frames") or {}
    except Exception:
        frames = {}
    print(f"OK: AppTest 0 exceptions; empty_session={not frames}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
