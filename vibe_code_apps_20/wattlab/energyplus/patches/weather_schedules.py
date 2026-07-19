"""Fan-availability Schedule:File IDF patch for weather-responsive schedules.

``apply_weather_schedule_file`` inserts a ``Schedule:File`` object pointing at
an hourly availability CSV (built by
:mod:`wattlab.existing_building.schedules`) and repoints fan availability
schedule references (``!- Schedule Name`` / ``!- Availability Schedule Name``
fields naming the target schedule, ``FanAvailSched`` on 5ZoneAirCooled-style
IDFs) at the new schedule.

When no fan availability reference is found the patch still inserts the
Schedule:File object but documents the manual-wiring surrogate in the
returned metadata instead of failing silently.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

_HEADER = "! WattLab weather schedule patch: weather_schedule_file"
_DEFAULT_TARGET = "FanAvailSched"


def _schedule_file_object(name: str, csv_path: str, hours_of_data: int) -> str:
    return (
        "Schedule:File,\n"
        f"    {name},  !- Name\n"
        "    Fraction,                !- Schedule Type Limits Name\n"
        f"    {csv_path},  !- File Name\n"
        "    2,                       !- Column Number\n"
        "    1,                       !- Rows to Skip at Top\n"
        f"    {hours_of_data},                    !- Number of Hours of Data\n"
        "    Comma,                   !- Column Separator\n"
        "    No,                      !- Interpolate to Timestep\n"
        "    60;                      !- Minutes per Item\n"
    )


def apply_weather_schedule_file(
    src: Path,
    dest: Path,
    schedule_csv: Path,
    schedule_name: str,
    *,
    target_schedule: str = _DEFAULT_TARGET,
) -> dict:
    """Insert a Schedule:File and repoint fan availability references to it."""
    src = Path(src)
    dest = Path(dest)
    schedule_csv = Path(schedule_csv)
    if not schedule_csv.is_file():
        raise ValueError(f"schedule_csv does not exist: {schedule_csv}")

    csv_text = schedule_csv.read_text(encoding="utf-8")
    data_rows = max(0, len(csv_text.splitlines()) - 1)  # minus header row
    hours_of_data = 8784 if data_rows >= 8784 else 8760

    flags: list[str] = ["conceptual_screening_schedule"]
    if data_rows not in (8760, 8784):
        flags.append("non_annual_schedule_rows")

    text = src.read_text(encoding="utf-8", errors="replace")

    # Repoint schedule *references* only: fields whose IDF comment is
    # 'Schedule Name' or 'Availability Schedule Name'. The target schedule's
    # own '!- Name' field is intentionally left alone.
    ref_re = re.compile(
        rf"(?m)^([ \t]*){re.escape(target_schedule)}"
        rf"([ \t]*[,;][ \t]*!-[ \t]*(?:Availability[ \t]+)?Schedule Name)"
    )
    text, references_repointed = ref_re.subn(
        lambda m: f"{m.group(1)}{schedule_name}{m.group(2)}", text
    )

    # Insert or replace the Schedule:File object (idempotent re-apply).
    csv_path_str = str(schedule_csv)
    schedule_object = _schedule_file_object(schedule_name, csv_path_str, hours_of_data)
    existing_re = re.compile(
        rf"(?ms)^[ \t]*Schedule:File,[ \t]*\r?\n"
        rf"[ \t]*{re.escape(schedule_name)},[^\r\n]*\r?\n"
        rf".*?;[^\r\n]*(?:\r?\n|$)"
    )
    if existing_re.search(text):
        # Lambda replacement: the object text may contain Windows paths whose
        # backslashes re.sub would otherwise treat as escape sequences.
        text = existing_re.sub(lambda _m: schedule_object, text)
    else:
        text = text.rstrip() + "\n\n" + schedule_object

    surrogate: str | None = None
    if references_repointed == 0:
        surrogate = (
            f"No fan availability schedule reference named {target_schedule!r} "
            "was found; the Schedule:File object was inserted but must be "
            "wired to an AvailabilityManager:Scheduled / fan availability "
            "field manually (documented surrogate)."
        )
        flags.append("fan_availability_reference_not_found_surrogate_documented")

    if _HEADER not in text:
        text = f"{_HEADER}\n{text}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")

    meta: dict[str, Any] = {
        "patch": "weather_schedule_file",
        "schedule_name": schedule_name,
        "schedule_csv": csv_path_str,
        "csv_sha256": hashlib.sha256(csv_text.encode("utf-8")).hexdigest(),
        "csv_rows": data_rows,
        "number_of_hours_of_data": hours_of_data,
        "target_schedule": target_schedule,
        "references_repointed": references_repointed,
        "surrogate": surrogate,
        "out": str(dest),
        "ok": True,
        "flags": flags,
    }
    return meta
