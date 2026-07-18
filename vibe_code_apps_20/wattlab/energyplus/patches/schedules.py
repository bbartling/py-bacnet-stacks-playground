"""Schedule patches: continuous (24/7) vs occupied office fan/coil availability."""

from __future__ import annotations

import re
from pathlib import Path

# Compact schedules used by sample 5ZoneAirCooled.idf
_TARGET_SCHEDULES = (
    "FanAvailSched",
    "CoolingCoilAvailSched",
    "ReheatCoilAvailSched",
)

CONTINUOUS_BODY = """    Fraction,                !- Schedule Type Limits Name
    Through: 12/31,          !- Field 1
    For: AllDays,            !- Field 2
    Until: 24:00,1.0;        !- Field 3
"""

# Weekday ~07:00–17:00 occupied, weekends off (except design days on).
OCCUPIED_OFFICE_BODY = """    Fraction,                !- Schedule Type Limits Name
    Through: 12/31,          !- Field 1
    For: WeekDays,           !- Field 2
    Until: 7:00,0.0,         !- Field 3
    Until: 17:00,1.0,        !- Field 5
    Until: 24:00,0.0,        !- Field 7
    For: SummerDesignDay WinterDesignDay, !- Field 9
    Until: 24:00,1.0,        !- Field 10
    For: AllOtherDays,       !- Field 12
    Until: 24:00,0.0;        !- Field 13
"""


def _replace_schedule_compact(idf_text: str, name: str, new_body: str) -> tuple[str, bool]:
    """Replace everything after the schedule name line through the terminating semicolon object."""
    # Match Schedule:Compact, <name>, ... until next blank-line-terminated object ending with ;
    pattern = re.compile(
        rf"(  Schedule:Compact,\s*\n\s*{re.escape(name)}\s*,[^\n]*\n)(.*?)(?=\n  [A-Za-z]|\n!- =+\n|\Z)",
        re.DOTALL,
    )
    m = pattern.search(idf_text)
    if not m:
        return idf_text, False
    # Keep the Schedule:Compact + Name lines; replace body
    replacement = m.group(1) + new_body.rstrip() + "\n"
    # Ensure we consumed through the original object's final semicolon
    return idf_text[: m.start()] + replacement + idf_text[m.end() :], True


def apply_named_avail_schedules(idf_text: str, body: str) -> tuple[str, list[str]]:
    applied: list[str] = []
    out = idf_text
    for name in _TARGET_SCHEDULES:
        out, ok = _replace_schedule_compact(out, name, body)
        if ok:
            applied.append(name)
    return out, applied


def apply_fan_avail_continuous(idf_path: Path, out_path: Path) -> dict:
    text = idf_path.read_text(encoding="utf-8", errors="replace")
    out, applied = apply_named_avail_schedules(text, CONTINUOUS_BODY)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out, encoding="utf-8")
    return {
        "patch": "fan_avail_continuous",
        "applied_schedules": applied,
        "out": str(out_path),
        "ok": bool(applied),
    }


def apply_fan_avail_occupied_office(idf_path: Path, out_path: Path) -> dict:
    text = idf_path.read_text(encoding="utf-8", errors="replace")
    out, applied = apply_named_avail_schedules(text, OCCUPIED_OFFICE_BODY)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out, encoding="utf-8")
    return {
        "patch": "fan_avail_occupied_office",
        "applied_schedules": applied,
        "out": str(out_path),
        "ok": bool(applied),
    }
