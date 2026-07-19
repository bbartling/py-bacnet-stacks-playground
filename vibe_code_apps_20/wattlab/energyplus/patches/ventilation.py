"""Outdoor-air fraction / damper-fault IDF patches (conceptual surrogates).

``apply_outdoor_air_fraction`` drives Controller:OutdoorAir minimum outdoor
air through a constant fraction schedule. This is a conceptual surrogate:
the schedule multiplies the controller's (auto)sized minimum OA flow, so
``min_oa_fraction`` is a fraction of design minimum OA, not of total supply
airflow. ``stuck_closed=True`` forces the fraction to 0.0 (OA damper stuck
closed fault).

Zeroing outdoor air must NOT zero envelope leakage: ZoneInfiltration objects
are deliberately left untouched and their preservation is verified.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_OA_SCHEDULE_NAME = "WattLab Min OA Fraction Sched"
_HEADER = "! WattLab ventilation patch: outdoor_air_fraction"

_INFILTRATION_TYPES = (
    "ZoneInfiltration:DesignFlowRate",
    "ZoneInfiltration:EffectiveLeakageArea",
    "ZoneInfiltration:FlowCoefficient",
)


def _object_blocks(text: str, object_type: str) -> list[str]:
    pattern = re.compile(
        rf"(?ms)^[ \t]*{re.escape(object_type)}[ \t]*,[ \t]*\r?\n"
        rf".*?;[^\r\n]*(?:\r?\n|$)"
    )
    return pattern.findall(text)


def _replace_field(text: str, comment: str, value: str) -> tuple[str, int]:
    pattern = re.compile(
        rf"(?m)^([ \t]*)([^,!;\r\n]*?)([,;][ \t]*!-[ \t]*"
        rf"{re.escape(comment)}[ \t]*)(\r?\n|$)"
    )
    return pattern.subn(
        lambda m: f"{m.group(1)}{value}{m.group(3)}{m.group(4)}", text
    )


def _oa_schedule_object(fraction: float) -> str:
    return (
        "Schedule:Compact,\n"
        f"    {_OA_SCHEDULE_NAME},  !- Name\n"
        "    Fraction,                !- Schedule Type Limits Name\n"
        "    Through: 12/31,          !- Field 1\n"
        "    For: AllDays,            !- Field 2\n"
        f"    Until: 24:00,{fraction:g};        !- Field 3\n"
    )


def apply_outdoor_air_fraction(
    src: Path,
    dest: Path,
    min_oa_fraction: float,
    *,
    stuck_closed: bool = False,
    economizer_disabled: bool = False,
) -> dict:
    """Set a constant minimum-OA fraction schedule on Controller:OutdoorAir."""
    min_oa_fraction = float(min_oa_fraction)
    if not 0.0 <= min_oa_fraction <= 1.0:
        raise ValueError("min_oa_fraction must be within [0, 1]")
    effective_fraction = 0.0 if stuck_closed else min_oa_fraction

    src = Path(src)
    dest = Path(dest)
    text = src.read_text(encoding="utf-8", errors="replace")

    controllers = _object_blocks(text, "Controller:OutdoorAir")
    if not controllers:
        raise ValueError("No target Controller:OutdoorAir objects found")
    infiltration_before = {
        t: _object_blocks(text, t) for t in _INFILTRATION_TYPES
    }

    # Point every OA controller's minimum-OA schedule at our constant schedule.
    pattern = re.compile(
        r"(?ms)^[ \t]*Controller:OutdoorAir[ \t]*,[ \t]*\r?\n"
        r".*?;[^\r\n]*(?:\r?\n|$)"
    )
    schedules_pointed = 0
    economizers_disabled = 0

    def patch_controller(match: re.Match[str]) -> str:
        nonlocal schedules_pointed, economizers_disabled
        block = match.group(0)
        block, n = _replace_field(
            block, "Minimum Outdoor Air Schedule Name", _OA_SCHEDULE_NAME
        )
        schedules_pointed += n
        if economizer_disabled:
            block, n = _replace_field(block, "Economizer Control Type", "NoEconomizer")
            economizers_disabled += n
        return block

    text = pattern.sub(patch_controller, text)
    if schedules_pointed == 0:
        raise ValueError(
            "No 'Minimum Outdoor Air Schedule Name' field found on "
            "Controller:OutdoorAir objects"
        )

    # Add or update the constant fraction schedule (idempotent re-apply).
    schedule_re = re.compile(
        rf"(?ms)^[ \t]*Schedule:Compact,[ \t]*\r?\n"
        rf"[ \t]*{re.escape(_OA_SCHEDULE_NAME)},[^\r\n]*\r?\n"
        rf".*?;[^\r\n]*(?:\r?\n|$)"
    )
    if schedule_re.search(text):
        text = schedule_re.sub(_oa_schedule_object(effective_fraction), text)
    else:
        text = text.rstrip() + "\n\n" + _oa_schedule_object(effective_fraction)

    # Hard guarantee: OA changes never alter envelope infiltration objects.
    infiltration_after = {t: _object_blocks(text, t) for t in _INFILTRATION_TYPES}
    if infiltration_after != infiltration_before:
        raise AssertionError("outdoor_air_fraction patch must not touch infiltration")
    infiltration_preserved = sum(len(v) for v in infiltration_before.values())

    if _HEADER not in text:
        text = f"{_HEADER}\n{text}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")

    flags = [
        "conceptual_ventilation_surrogate",
        "min_oa_fraction_of_design_min_oa_not_supply_flow",
        "screening_only",
    ]
    if stuck_closed:
        flags.append("oa_damper_stuck_closed_surrogate")
    if economizer_disabled:
        flags.append("economizer_disabled")
    if effective_fraction == 0.0:
        flags.append("zero_oa_infiltration_preserved")

    meta: dict[str, Any] = {
        "patch": "outdoor_air_fraction",
        "min_oa_fraction": min_oa_fraction,
        "effective_fraction": effective_fraction,
        "stuck_closed": stuck_closed,
        "economizer_disabled": economizer_disabled,
        "controllers_patched": schedules_pointed,
        "economizers_patched": economizers_disabled,
        "oa_schedule": _OA_SCHEDULE_NAME,
        "infiltration_objects_preserved": infiltration_preserved,
        "out": str(dest),
        "ok": schedules_pointed > 0,
        "flags": flags,
    }
    return meta
