"""Guideline 36 airside proxies via IDF field edits (not full G36 sequences)."""

from __future__ import annotations

import re
from pathlib import Path


def _set_vav_min_fraction(text: str, fraction: float) -> tuple[str, int]:
    """Lower Constant Minimum Air Flow Fraction on VAV:Reheat terminals."""
    count = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f"{m.group(1)}{fraction:.2f}{m.group(3)}"

    # Match lines like:    0.3,                     !- Constant Minimum Air Flow Fraction
    new, n = re.subn(
        r"(^[ \t]*)([0-9.]+)(,[ \t]*!- Constant Minimum Air Flow Fraction[ \t]*$)",
        repl,
        text,
        flags=re.MULTILINE,
    )
    return new, n


def _set_fan_pressure_rise(text: str, pressure_pa: float) -> tuple[str, int]:
    """Reduce Fan:VariableVolume Pressure Rise (duct static reset proxy)."""
    count = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f"{m.group(1)}{pressure_pa:.1f}{m.group(3)}"

    new, n = re.subn(
        r"(^[ \t]*)([0-9.]+)(,[ \t]*!- Pressure Rise \{Pa\}[ \t]*$)",
        repl,
        text,
        flags=re.MULTILINE,
    )
    return new, n


def _set_fan_power_min_fraction(text: str, fraction: float) -> tuple[str, int]:
    count = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f"{m.group(1)}{fraction:.2f}{m.group(3)}"

    new, n = re.subn(
        r"(^[ \t]*)([0-9.]+)(,[ \t]*!- Fan Power Minimum Flow Fraction[ \t]*$)",
        repl,
        text,
        flags=re.MULTILINE,
    )
    return new, n


def apply_gl36_airside_proxy(
    idf_path: Path,
    out_path: Path,
    *,
    vav_min_fraction: float = 0.15,
    fan_pressure_pa: float = 400.0,
    fan_power_min_fraction: float = 0.15,
) -> dict:
    """
    Conceptual G36 airside proxy:
    - VAV box minimum ~0.30 → 0.15
    - Fan pressure rise reduction (DSP-reset / fan power proxy)
    - Fan power minimum flow fraction reduced
    """
    text = idf_path.read_text(encoding="utf-8", errors="replace")
    text, n_vav = _set_vav_min_fraction(text, vav_min_fraction)
    text, n_press = _set_fan_pressure_rise(text, fan_pressure_pa)
    text, n_fmin = _set_fan_power_min_fraction(text, fan_power_min_fraction)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "! App20 IDF patch: conceptual_gl36_proxy "
        f"(vav_min={vav_min_fraction}, fan_Pa={fan_pressure_pa}, "
        f"fan_min_frac={fan_power_min_fraction}); NOT full ASHRAE Guideline 36\n"
    )
    if not text.lstrip().startswith("!"):
        text = header + text
    else:
        text = header + text
    out_path.write_text(text, encoding="utf-8")
    return {
        "patch": "gl36_airside_proxy",
        "vav_terminals_patched": n_vav,
        "fans_pressure_patched": n_press,
        "fans_min_frac_patched": n_fmin,
        "out": str(out_path),
        "ok": n_vav > 0 or n_press > 0,
        "flags": ["conceptual_gl36_proxy", "gl36_proxy_not_full_sequences"],
    }
