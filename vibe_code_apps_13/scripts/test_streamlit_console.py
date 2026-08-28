#!/usr/bin/env python3
"""Smoke-test Streamlit supervisory console (no browser)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from streamlit.testing.v1 import AppTest


def main() -> int:
    app = AppTest.from_file(ROOT / "tools" / "supervisory_console.py", default_timeout=60)
    app.run()
    if app.exception:
        print("APP EXCEPTION:", app.exception[0].value)
        return 1

    titles = [m.value for m in app.subheader]
    for need in (
        "Lab console — run control + live trunk",
        "Phase 2 — rusty-bacnet MS/TP",
    ):
        if need not in titles:
            print("Missing subheader:", need, "have:", titles)
            return 1

    labels = [b.label for b in app.button]
    for need in (
        "▶ Start wire test",
        "⏹ Stop",
        "🧹 Clear stale state",
        "🔨 Build release",
        "🧪 Loopback acceptance",
    ):
        if need not in labels:
            print("Missing button:", need, "have:", labels)
            return 1

    # Clear stale state should always work.
    clear_idx = labels.index("🧹 Clear stale state")
    app.button[clear_idx].click().run()
    if app.exception:
        print("CLEAR EXCEPTION:", app.exception[0].value)
        return 1

    print("OK: supervisory console renders, buttons present, clear-stale works.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
