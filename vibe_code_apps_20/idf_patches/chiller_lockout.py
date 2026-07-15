"""Chiller / CHW loop lockout at low outdoor air temperature.

Raises AvailabilityManager:LowTemperatureTurnOff threshold so mechanical
cooling does not run below a screening OAT (default 12.8 C / 55 F).
Matches OpenFDD MECH-OAT-1 style findings.
"""

from __future__ import annotations

import re
from pathlib import Path


def f_to_c(temp_f: float) -> float:
    return (temp_f - 32.0) * 5.0 / 9.0


def apply_chiller_lockout(
    idf_path: Path,
    out_path: Path,
    *,
    oat_lockout_f: float = 55.0,
) -> dict:
    """
    Raise LowTemperatureTurnOff on CHW plant availability managers.

    Prototype 5ZoneAirCooled already has CW Low Temp Limit at 2.0 C (~35.6 F).
    This ECM raises it to oat_lockout_f (screening default 55 F / ~12.8 C).
    """
    text = idf_path.read_text(encoding="utf-8", errors="replace")
    temp_c = round(f_to_c(oat_lockout_f), 1)
    lines = text.splitlines(keepends=True)
    out_lines: list[str] = []
    in_block = False
    patched = 0

    for line in lines:
        if re.match(r"\s*AvailabilityManager:LowTemperatureTurnOff\s*,", line):
            in_block = True
        if in_block and "!- Temperature {C}" in line:
            m = re.match(r"^([ \t]*)([0-9.]+)(,[ \t]*!- Temperature \{C\}[ \t]*)(\r?\n)?$", line)
            if m:
                nl = m.group(4) or "\n"
                line = f"{m.group(1)}{temp_c}{m.group(3)}{nl}"
                patched += 1
                in_block = False
            else:
                in_block = False
        elif in_block and line.strip().endswith(";"):
            in_block = False
        out_lines.append(line)

    new = "".join(out_lines)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"! App20 IDF patch: chiller_lockout "
        f"(oat_lockout_f={oat_lockout_f}, temp_c={temp_c})\n"
    )
    out_path.write_text(header + new, encoding="utf-8")
    return {
        "patch": "chiller_lockout",
        "oat_lockout_f": oat_lockout_f,
        "temperature_c": temp_c,
        "managers_patched": patched,
        "out": str(out_path),
        "ok": patched > 0,
        "flags": ["chiller_lockout_screening", "mech_oat_proxy"],
    }
