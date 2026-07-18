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


# Monthly Output:Meter objects (NOT MeterFileOnly) are what make EnergyPlus
# emit the tabular "BUILDING ENERGY PERFORMANCE - <FUEL>" monthly sections in
# eplustbl that wattlab.energyplus.results.parse_monthly_energy reads. The
# bundled 5ZoneAirCooled prototype only requests MeterFileOnly meters, so
# without this patch every run has empty `monthly` and the ASHRAE G14 bill
# gate silently never fires (found in the Liberty twin-loop rehearsal).
MONTHLY_TABLE_OUTPUTS: list[tuple[str, str]] = [
    (
        "output:meter,electricity:facility,monthly",
        "  Output:Meter,Electricity:Facility,Monthly;",
    ),
    (
        "output:meter,naturalgas:facility,monthly",
        "  Output:Meter,NaturalGas:Facility,Monthly;",
    ),
]


def _ensure_lines(
    idf_path: Path,
    out_path: Path,
    pairs: list[tuple[str, str]],
    patch_name: str,
) -> dict[str, Any]:
    text = idf_path.read_text(encoding="utf-8", errors="replace")
    lower = text.lower()
    added: list[str] = []
    for needle, line in pairs:
        if needle in lower:
            continue
        text = text.rstrip() + "\n\n" + line + "\n"
        lower = text.lower()
        added.append(line.strip())

    out_path.write_text(text, encoding="utf-8")
    return {
        "patch": patch_name,
        "added": added,
        "out": str(out_path),
    }


def apply_hourly_outputs(idf_path: Path, out_path: Path) -> dict[str, Any]:
    """Append missing calibration output objects (idempotent)."""
    return _ensure_lines(idf_path, out_path, CALIBRATION_OUTPUTS, "hourly_outputs")


def apply_monthly_energy_tables(idf_path: Path, out_path: Path) -> dict[str, Any]:
    """Ensure monthly facility meters so eplustbl carries monthly fuel tables."""
    return _ensure_lines(idf_path, out_path, MONTHLY_TABLE_OUTPUTS, "monthly_energy_tables")
