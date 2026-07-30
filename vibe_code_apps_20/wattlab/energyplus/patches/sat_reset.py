"""Supply-air / leaving-air temperature reset (prototype + Liberty Twin paths)."""

from __future__ import annotations

import re
from pathlib import Path

# Warmer summer SAT / more aggressive shoulder reset vs prototype defaults
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
_LIBERTY_SAT_SCH = "WattLab SAT Reset Cooling"
_LIBERTY_WINTER_SAT_C = 12.8
_LIBERTY_COOLING_SAT_C = 14.0  # warmer leaving-air (°C) screening raise


def _inject_liberty_cooling_sat(text: str) -> tuple[str, int]:
    """Reset every Liberty VAV cooling SPM without changing its winter DAT path."""
    sch_block = (
        f"Schedule:Compact,\n"
        f"  {_LIBERTY_SAT_SCH},\n"
        f"  Temperature,\n"
        f"  Through: 3/31,\n"
        f"  For: AllDays,\n"
        f"  Until: 24:00,{_LIBERTY_WINTER_SAT_C},\n"
        f"  Through: 9/30,\n"
        f"  For: AllDays,\n"
        f"  Until: 24:00,{_LIBERTY_COOLING_SAT_C},\n"
        f"  Through: 12/31,\n"
        f"  For: AllDays,\n"
        f"  Until: 24:00,{_LIBERTY_WINTER_SAT_C};\n\n"
    )

    # Do not match the heating managers: their schedule is the winter DAT
    # evidence and must remain untouched.  Match every cooling manager so a
    # dual-AHU Liberty model cannot silently patch only VAV Sys 1.
    cooling_spm = re.compile(
        r"(SetpointManager:Scheduled,\s*\n\s*[^\n,]*Cooling Supply Air Temp Manager,[^\n]*\n"
        r"\s*Temperature,[^\n]*\n\s*)([^,\n]+)(,)",
        re.IGNORECASE,
    )
    first = cooling_spm.search(text)
    if first is None:
        return text, 0

    if _LIBERTY_SAT_SCH not in text:
        text = text[: first.start()] + sch_block + text[first.start() :]

    new, n = cooling_spm.subn(
        rf"\g<1>{_LIBERTY_SAT_SCH}\3",
        text,
    )
    return new, n


def apply_sat_reset(idf_path: Path, out_path: Path) -> dict:
    """Widen seasonal SAT band, or reset all Liberty cooling AHUs."""
    text = idf_path.read_text(encoding="utf-8", errors="replace")
    flags: list[str] = ["sat_reset_proxy", "not_full_gl36_sat_reset"]
    ok = False
    mode = "none"
    managers_patched = 0

    pattern = re.compile(
        rf"(  Schedule:Compact,\s*\n\s*{re.escape(_SCHEDULE_NAME)}\s*,[^\n]*\n)"
        rf"(.*?)(?=\n  [A-Za-z]|\n!- =+\n|\Z)",
        re.DOTALL,
    )
    m = pattern.search(text)
    if m:
        text = text[: m.start()] + m.group(1) + SAT_RESET_BODY.rstrip() + "\n" + text[m.end() :]
        ok = True
        mode = "seasonal_schedule"

    if not ok:
        text, managers_patched = _inject_liberty_cooling_sat(text)
        if managers_patched:
            ok = True
            mode = "liberty_cooling_spms"
            flags.extend(["liberty_vav_sat_spm", "liberty_dual_ahu_sat_spm"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = f"! App20 IDF patch: sat_reset (mode={mode}; not full G36 SAT reset)\n"
    out_path.write_text(header + text, encoding="utf-8")
    return {
        "patch": "sat_reset",
        "schedule": _SCHEDULE_NAME if mode == "seasonal_schedule" else _LIBERTY_SAT_SCH,
        "mode": mode,
        "out": str(out_path),
        "ok": ok,
        "flags": flags,
        "managers_patched": managers_patched,
    }
