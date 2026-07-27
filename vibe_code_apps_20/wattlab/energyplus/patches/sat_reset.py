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
_LIBERTY_SAT_C = 14.0  # warmer leaving-air (°C) screening raise


def _inject_liberty_cooling_sat(text: str) -> tuple[str, bool]:
    """Point VAV cooling SPM at a constant warmer SAT schedule (Liberty / HVACTemplate)."""
    sch_block = (
        f"Schedule:Compact,\n"
        f"  {_LIBERTY_SAT_SCH},\n"
        f"  Temperature,\n"
        f"  Through: 12/31,\n"
        f"  For: AllDays,\n"
        f"  Until: 24:00,{_LIBERTY_SAT_C};\n\n"
    )
    if _LIBERTY_SAT_SCH not in text:
        anchor = "SetpointManager:Scheduled,\n  VAV Sys 1 Cooling Supply Air Temp Manager,"
        if anchor in text:
            text = text.replace(anchor, sch_block + anchor, 1)
        else:
            text = sch_block + text

    new, n = re.subn(
        r"(SetpointManager:Scheduled,\s*\n\s*VAV Sys 1 Cooling Supply Air Temp Manager,[^\n]*\n"
        r"\s*Temperature,[^\n]*\n\s*)([^,\n]+)(,)",
        rf"\g<1>{_LIBERTY_SAT_SCH}\3",
        text,
        count=1,
    )
    return new, n > 0


def apply_sat_reset(idf_path: Path, out_path: Path) -> dict:
    """Widen seasonal SAT band, or retarget Liberty cooling SPM to warmer SAT."""
    text = idf_path.read_text(encoding="utf-8", errors="replace")
    flags: list[str] = ["sat_reset_proxy", "not_full_gl36_sat_reset"]
    ok = False
    mode = "none"

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
        text, hit = _inject_liberty_cooling_sat(text)
        if hit:
            ok = True
            mode = "liberty_cooling_spm"
            flags.append("liberty_vav_sat_spm")

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
    }
