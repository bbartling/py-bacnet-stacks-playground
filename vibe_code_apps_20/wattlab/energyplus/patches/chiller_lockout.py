"""Chiller / CHW loop lockout at low outdoor air temperature.

Raises AvailabilityManager:LowTemperatureTurnOff threshold so mechanical
cooling does not run below a screening OAT (default 15.6 C / 60 F for G36 story).
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
    oat_lockout_f: float = 60.0,
) -> dict:
    """
    Raise LowTemperatureTurnOff on CHW plant availability managers.

    Accepts both commented ``!- Temperature {C}`` lines and bare numeric
    terminators (Liberty Twin: ``  7.22;``).
    """
    text = idf_path.read_text(encoding="utf-8", errors="replace")
    temp_c = round(f_to_c(oat_lockout_f), 1)
    lines = text.splitlines(keepends=True)
    out_lines: list[str] = []
    in_block = False
    patched = 0

    for line in lines:
        # Object definition (not a list "Object Type" reference)
        if re.match(r"\s*AvailabilityManager:LowTemperatureTurnOff\s*,", line) and (
            "!- Availability Manager Object Type" not in line
        ):
            in_block = True
            out_lines.append(line)
            continue
        if in_block:
            # Commented temperature field
            m = re.match(
                r"^([ \t]*)([0-9.]+)(,[ \t]*!- Temperature \{C\}[ \t]*)(\r?\n)?$",
                line,
            )
            if m:
                nl = m.group(4) or "\n"
                line = f"{m.group(1)}{temp_c}{m.group(3)}{nl}"
                patched += 1
                in_block = False
                out_lines.append(line)
                continue
            # Bare last field, optional trailing comment: "  7.22;  !- Temperature"
            m2 = re.match(
                r"^([ \t]*)([0-9.]+)(;[ \t]*(?:!-.*)?)$",
                line.rstrip("\r\n"),
            )
            if m2:
                nl = "\n" if line.endswith("\n") else ("\r\n" if line.endswith("\r\n") else "\n")
                # Preserve a short comment if present
                comment = ""
                if "!-" in (m2.group(3) or ""):
                    comment = "                                                    !- Temperature"
                line = f"{m2.group(1)}{temp_c};{comment}{nl}"
                patched += 1
                in_block = False
                out_lines.append(line)
                continue
            if line.strip().endswith(";"):
                in_block = False
        out_lines.append(line)

    new = "".join(out_lines)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"! App20 IDF patch: chiller_lockout "
        f"(oat_lockout_f={oat_lockout_f}, temp_c={temp_c}, managers_patched={patched})\n"
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
