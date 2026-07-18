"""Patch RunPeriod begin/end dates for overlap-window calibration."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any


def _parse_ts(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip().replace("Z", "+00:00")
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return None


def apply_run_period(
    idf_path: Path,
    out_path: Path,
    *,
    begin: str | datetime,
    end: str | datetime,
) -> dict[str, Any]:
    """Set the first RunPeriod object's begin/end month, day, and year."""
    b = _parse_ts(begin)
    e = _parse_ts(end)
    if b is None or e is None:
        raise ValueError(f"Could not parse RunPeriod dates: begin={begin!r} end={end!r}")

    text = idf_path.read_text(encoding="utf-8", errors="replace")

    # Match a full RunPeriod object (non-greedy until trailing ;)
    pattern = re.compile(
        r"(RunPeriod\s*,)(.*?)(;)",
        re.IGNORECASE | re.DOTALL,
    )

    def _replace(m: re.Match[str]) -> str:
        body = m.group(2)
        # Split on commas that separate fields (ignore commas inside comments by
        # working line-oriented).
        lines = body.splitlines(keepends=True)
        # Collect field values in order (skip blank / pure-comment lines)
        field_lines: list[tuple[int, str]] = []
        for i, line in enumerate(lines):
            code = line.split("!-")[0].strip()
            if not code:
                continue
            field_lines.append((i, line))

        # field_lines[0] = Name; then Begin Month, Day, Year, End Month, Day, Year
        updates = {
            1: (b.month, "Begin Month"),
            2: (b.day, "Begin Day of Month"),
            3: (b.year, "Begin Year"),
            4: (e.month, "End Month"),
            5: (e.day, "End Day of Month"),
            6: (e.year, "End Year"),
        }
        for fi, (val, comment) in updates.items():
            if fi >= len(field_lines):
                break
            li, old = field_lines[fi]
            indent_m = re.match(r"^(\s*)", old)
            indent = indent_m.group(1) if indent_m else "    "
            lines[li] = f"{indent}{val},{' ' * max(1, 24 - len(str(val)))}!- {comment}\n"

        return m.group(1) + "".join(lines) + m.group(3)

    new_text, n = pattern.subn(_replace, text, count=1)
    if n == 0:
        raise ValueError(f"No RunPeriod object found in {idf_path}")

    out_path.write_text(new_text, encoding="utf-8")
    return {
        "patch": "run_period",
        "begin": f"{b.year}-{b.month:02d}-{b.day:02d}",
        "end": f"{e.year}-{e.month:02d}-{e.day:02d}",
        "objects_patched": n,
        "out": str(out_path),
    }
