"""Ensure calibration-friendly hourly Output:Variable / Meter lines exist."""

from __future__ import annotations

from pathlib import Path
from typing import Any

# (needle_substring_lower, full_idf_line)
CALIBRATION_OUTPUTS: list[tuple[str, str]] = [
    (
        "fan electricity rate",
        "  Output:Variable,*,Fan Electricity Rate,Hourly;",
    ),
    (
        "fan electricity energy",
        "  Output:Variable,*,Fan Electricity Energy,Hourly;",
    ),
    (
        "output:meter,electricity:facility,hourly",
        "  Output:Meter,Electricity:Facility,Hourly;",
    ),
]


def apply_hourly_outputs(idf_path: Path, out_path: Path) -> dict[str, Any]:
    """Append missing calibration output objects (idempotent)."""
    text = idf_path.read_text(encoding="utf-8", errors="replace")
    lower = text.lower()
    added: list[str] = []
    for needle, line in CALIBRATION_OUTPUTS:
        if needle in lower:
            continue
        text = text.rstrip() + "\n\n" + line + "\n"
        lower = text.lower()
        added.append(line.strip())

    out_path.write_text(text, encoding="utf-8")
    return {
        "patch": "hourly_outputs",
        "added": added,
        "out": str(out_path),
    }
