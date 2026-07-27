"""Schedule patches: continuous (24/7) vs occupied office fan/coil availability."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

# Compact schedules used by sample 5ZoneAirCooled.idf
_TARGET_SCHEDULES = (
    "FanAvailSched",
    "CoolingCoilAvailSched",
    "ReheatCoilAvailSched",
)

# Large-office / stacked prototypes often use these names instead.
_EXTRA_OPERATION_SCHEDULES = (
    "HVACOperationSchd",
)

CONTINUOUS_BODY_COMMENT = """    Fraction,                !- Schedule Type Limits Name
    Through: 12/31,          !- Field 1
    For: AllDays,            !- Field 2
    Until: 24:00,1.0;        !- Field 3
"""

CONTINUOUS_BODY_INLINE = """    Through: 12/31, For: AllDays, Until: 24:00, 1.0;
"""

# Weekday ~07:00–17:00 occupied, weekends off (except design days on).
OCCUPIED_OFFICE_BODY_COMMENT = """    Fraction,                !- Schedule Type Limits Name
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

OCCUPIED_OFFICE_BODY_INLINE = """    Through: 12/31,
    For: WeekDays,
    Until: 7:00,0.0, Until: 17:00,1.0, Until: 24:00,0.0,
    For: SummerDesignDay WinterDesignDay,
    Until: 24:00,1.0,
    For: AllOtherDays,
    Until: 24:00,0.0;
"""


def discover_operation_schedule_names(idf_text: str) -> list[str]:
    """Schedules referenced as fan / system / equipment availability in the IDF."""
    found: set[str] = set()
    for m in re.finditer(
        r"^\s*([^,;!\n]+)\s*,\s*!-\s*(?:Fan Schedule Name|System Availability Schedule Name|Availability Schedule Name)",
        idf_text,
        re.MULTILINE,
    ):
        name = m.group(1).strip()
        if name:
            found.add(name)
    for hint in _EXTRA_OPERATION_SCHEDULES:
        if re.search(
            rf"(?m)^\s*Schedule:Compact,\s*\n\s*{re.escape(hint)}\s*,",
            idf_text,
        ):
            found.add(hint)
    return sorted(found)


def _schedule_names_to_try(idf_text: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for name in (*_TARGET_SCHEDULES, *discover_operation_schedule_names(idf_text)):
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _replace_schedule_compact(
    idf_text: str,
    name: str,
    body_fn: Callable[[bool], str],
) -> tuple[str, bool]:
    """Replace a full Schedule:Compact object (stacked inline or comment-style IDFs)."""
    pat = re.compile(
        rf"(?ms)^(\s*)Schedule:Compact,\s*\n\s*{re.escape(name)}\s*,([^\n]*)\n.*?(;[^\n]*\n)",
    )
    m = pat.search(idf_text)
    if not m:
        return idf_text, False
    indent = m.group(1) or ""
    name_tail = m.group(2)
    comment_style = "!-" in name_tail or "!-" in m.group(0)
    type_lim = name_tail.split("!-")[0].strip().rstrip(",").strip()
    if not type_lim:
        type_lim = "Fraction"
    inner = indent + "    "
    body = body_fn(comment_style)
    new_obj = (
        f"{indent}Schedule:Compact,\n"
        f"{inner}{name}, {type_lim},\n"
        f"{body.rstrip()}\n"
    )
    return idf_text[: m.start()] + new_obj + idf_text[m.end() :], True


def apply_named_avail_schedules(
    idf_text: str,
    body_fn: Callable[[bool], str],
    *,
    schedule_names: list[str] | None = None,
) -> tuple[str, list[str]]:
    applied: list[str] = []
    out = idf_text
    names = schedule_names if schedule_names is not None else _schedule_names_to_try(idf_text)
    for name in names:
        out, ok = _replace_schedule_compact(out, name, body_fn)
        if ok:
            applied.append(name)
    return out, applied


def apply_fan_avail_continuous(idf_path: Path, out_path: Path) -> dict:
    text = idf_path.read_text(encoding="utf-8", errors="replace")

    def body(comment: bool) -> str:
        return CONTINUOUS_BODY_COMMENT if comment else CONTINUOUS_BODY_INLINE

    out, applied = apply_named_avail_schedules(text, body)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out, encoding="utf-8")
    return {
        "patch": "fan_avail_continuous",
        "applied_schedules": applied,
        "discovered_schedules": discover_operation_schedule_names(text),
        "out": str(out_path),
        "ok": bool(applied),
    }


def apply_fan_avail_occupied_office(idf_path: Path, out_path: Path) -> dict:
    text = idf_path.read_text(encoding="utf-8", errors="replace")

    def body(comment: bool) -> str:
        return OCCUPIED_OFFICE_BODY_COMMENT if comment else OCCUPIED_OFFICE_BODY_INLINE

    out, applied = apply_named_avail_schedules(text, body)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out, encoding="utf-8")
    return {
        "patch": "fan_avail_occupied_office",
        "applied_schedules": applied,
        "discovered_schedules": discover_operation_schedule_names(text),
        "out": str(out_path),
        "ok": bool(applied),
    }
