"""Duct static pressure reset proxy — lower Fan:VariableVolume pressure rise."""

from __future__ import annotations

from pathlib import Path

from wattlab.energyplus.patches.gl36_proxy import _set_fan_pressure_rise


def apply_dsp_reset(
    idf_path: Path,
    out_path: Path,
    *,
    fan_pressure_pa: float = 450.0,
) -> dict:
    """Screening DSP-reset proxy: reduce fan pressure rise (Pa).

    Not full G36 trim-and-respond — moves fan energy on Twin models that use
    ``Fan:VariableVolume`` with a ``Pressure Rise {Pa}`` field.
    """
    text = idf_path.read_text(encoding="utf-8", errors="replace")
    text, n = _set_fan_pressure_rise(text, fan_pressure_pa)
    header = (
        f"! App20 IDF patch: dsp_reset "
        f"(fan_pressure_pa={fan_pressure_pa}, fans_patched={n})\n"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(header + text, encoding="utf-8")
    return {
        "patch": "dsp_reset",
        "fan_pressure_pa": fan_pressure_pa,
        "fans_patched": n,
        "out": str(out_path),
        "ok": n > 0,
        "flags": ["dsp_reset_pressure_proxy", "not_full_g36_trim_respond"],
    }
