"""Supply-air-temperature reset proxy (seasonal schedule shift).

Separable from the GL36 bundle so progressive measure savings can show
SAT-reset increment alone (responsive-defaults individual measures).
"""

from __future__ import annotations

import re
from pathlib import Path

# Warmer summer SAT / more aggressive shoulder reset vs prototype defaults
# (prototype: winter/shoulder 16 C, summer 13 C).
SAT_RESET_BODY = """    Temperature,             !- Schedule Type Limits Name
    Through: 3/31,           !- Field 1
    For: AllDays,            !- Field 2
    Until: 24:00,18.0,       !- Field 3
    Through: 9/30,           !- Field 5
    For: AllDays,            !- Field 6
    Until: 24:00,14.0,       !- Field 7
    Through: 12/31,          !- Field 9
    For: AllDays,            !- Field 10
    Until: 24:00,18.0;       !- Field 11
"""

_SCHEDULE_NAME = "Seasonal Reset Supply Air Temp Sch"


def apply_sat_reset(idf_path: Path, out_path: Path) -> dict:
    """Widen seasonal SAT reset band (screening proxy, not full G36 SAT reset)."""
    text = idf_path.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(
        rf"(  Schedule:Compact,\s*\n\s*{re.escape(_SCHEDULE_NAME)}\s*,[^\n]*\n)"
        rf"(.*?)(?=\n  [A-Za-z]|\n!- =+\n|\Z)",
        re.DOTALL,
    )
    m = pattern.search(text)
    ok = False
    if m:
        text = text[: m.start()] + m.group(1) + SAT_RESET_BODY.rstrip() + "\n" + text[m.end() :]
        ok = True

    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = "! App20 IDF patch: sat_reset (seasonal schedule proxy; not full G36 SAT reset)\n"
    out_path.write_text(header + text, encoding="utf-8")
    return {
        "patch": "sat_reset",
        "schedule": _SCHEDULE_NAME,
        "out": str(out_path),
        "ok": ok,
        "flags": ["sat_reset_proxy", "not_full_gl36_sat_reset"],
    }
