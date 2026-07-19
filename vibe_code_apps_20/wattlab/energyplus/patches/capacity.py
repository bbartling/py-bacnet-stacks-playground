"""Capacity-factor IDF patch: scale (or freeze) equipment sizing fields.

Conceptual right-sizing / oversizing screen for the 5ZoneAirCooled-style
prototype. Categories map onto explicit IDF fields:

  cooling_plant     Chiller:Electric               Nominal Capacity {W}
  heating_plant     Boiler:HotWater                Nominal Capacity {W}
  supply_airflow    Fan:VariableVolume             Maximum Flow Rate {m3/s}
  cooling_coils     Coil:Cooling:Water             Design Water Flow Rate {m3/s}  (surrogate)
  heating_coils     Coil:Heating:Water             Rated Capacity {W},
                                                   Maximum Water Flow Rate {m3/s},
                                                   U-Factor Times Area Value {W/K}
  terminal_airflow  AirTerminal:SingleDuct:VAV:Reheat  Maximum Air Flow Rate {m3/s}
  fan_pressure      Fan:VariableVolume             Pressure Rise {Pa}
  fan_power         Fan:VariableVolume             Pressure Rise {Pa}  (surrogate)

Documented surrogates:
  - ``cooling_coils`` scales the coil design water flow because
    Coil:Cooling:Water carries no rated-capacity field; water-side flow is a
    conceptual stand-in for coil capacity.
  - ``fan_power`` scales Pressure Rise because Fan:VariableVolume has no
    direct power field; power tracks flow x pressure / efficiency.

Numeric fields are multiplied by the factor. ``autosize`` fields are frozen
to ``inventory_value * factor`` when a sizing inventory resolver can supply
the simulated design value, otherwise they are left autosized and reported
as unresolved.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Callable, Mapping

# category -> list of (object_type, field_comment, surrogate_flag_or_None)
CAPACITY_FIELD_MAP: dict[str, list[tuple[str, str, str | None]]] = {
    "cooling_plant": [("Chiller:Electric", "Nominal Capacity {W}", None)],
    "heating_plant": [("Boiler:HotWater", "Nominal Capacity {W}", None)],
    "supply_airflow": [("Fan:VariableVolume", "Maximum Flow Rate {m3/s}", None)],
    "cooling_coils": [
        (
            "Coil:Cooling:Water",
            "Design Water Flow Rate {m3/s}",
            "cooling_coil_capacity_scaled_via_water_flow_surrogate",
        ),
    ],
    "heating_coils": [
        ("Coil:Heating:Water", "Rated Capacity {W}", None),
        ("Coil:Heating:Water", "Maximum Water Flow Rate {m3/s}", None),
        ("Coil:Heating:Water", "U-Factor Times Area Value {W/K}", None),
    ],
    "terminal_airflow": [
        ("AirTerminal:SingleDuct:VAV:Reheat", "Maximum Air Flow Rate {m3/s}", None),
    ],
    "fan_pressure": [("Fan:VariableVolume", "Pressure Rise {Pa}", None)],
    "fan_power": [
        (
            "Fan:VariableVolume",
            "Pressure Rise {Pa}",
            "fan_power_scaled_via_pressure_rise_surrogate",
        ),
    ],
}

# resolver(object_type, object_name, field_comment) -> design value or None
Resolver = Callable[[str, str, str], float | None]


def _object_pattern(object_type: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?ms)^[ \t]*{re.escape(object_type)}[ \t]*,[ \t]*\r?\n"
        rf".*?;[^\r\n]*(?:\r?\n|$)"
    )


def _object_name(block: str) -> str:
    m = re.search(r"(?m)^[ \t]*([^,;!\r\n]*?)[ \t]*,[ \t]*!-?[ \t]*Name[ \t]*$", block)
    if m:
        return m.group(1).strip()
    # Fallback: first field after the object-type header line.
    lines = block.splitlines()
    if len(lines) > 1:
        return lines[1].split("!")[0].strip().rstrip(",;").strip()
    return ""


def _field_pattern(comment: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?m)^([ \t]*)([^,!;\r\n]*?)([,;][ \t]*!-[ \t]*"
        rf"{re.escape(comment)}[ \t]*)(\r?\n|$)"
    )


def _format_value(value: float) -> str:
    return f"{value:.6g}"


def _validated_factors(factors: Mapping[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for category, raw in factors.items():
        if category not in CAPACITY_FIELD_MAP:
            known = ", ".join(sorted(CAPACITY_FIELD_MAP))
            raise ValueError(f"Unknown capacity category {category!r}; known: {known}")
        value = float(raw)
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"Capacity factor for {category!r} must be finite and > 0")
        out[category] = value
    return out


def scale_capacity_fields(
    text: str,
    factors: Mapping[str, Any],
    *,
    resolver: Resolver | None = None,
) -> tuple[str, dict[str, Any]]:
    """Apply capacity factors to IDF text; returns (new_text, meta).

    Shared engine for apply_capacity_factors and
    wattlab.energyplus.sizing.freeze_autosized_values.
    """
    validated = _validated_factors(factors)
    changes: list[dict[str, Any]] = []
    flags: set[str] = set()

    for category, factor in validated.items():
        for object_type, comment, surrogate in CAPACITY_FIELD_MAP[category]:
            pattern = _object_pattern(object_type)
            field_re = _field_pattern(comment)

            def patch_block(match: re.Match[str]) -> str:
                block = match.group(0)
                name = _object_name(block)

                def patch_field(fm: re.Match[str]) -> str:
                    raw = fm.group(2).strip()
                    change: dict[str, Any] = {
                        "category": category,
                        "object_type": object_type,
                        "object": name,
                        "field": comment,
                        "before": raw,
                    }
                    if raw.lower() in {"autosize", "autocalculate"}:
                        design = (
                            resolver(object_type, name, comment) if resolver else None
                        )
                        if design is None:
                            change["action"] = "left_autosize"
                            change["after"] = raw
                            changes.append(change)
                            return fm.group(0)
                        new_value = design * factor
                        change["action"] = "frozen"
                        change["design_value"] = design
                    else:
                        try:
                            current = float(raw)
                        except ValueError:
                            change["action"] = "skipped_non_numeric"
                            change["after"] = raw
                            changes.append(change)
                            return fm.group(0)
                        new_value = current * factor
                        change["action"] = "scaled"
                    formatted = _format_value(new_value)
                    change["after"] = formatted
                    changes.append(change)
                    if surrogate:
                        flags.add(surrogate)
                    return f"{fm.group(1)}{formatted}{fm.group(3)}{fm.group(4)}"

                return field_re.sub(patch_field, block)

            text = pattern.sub(patch_block, text)

    scaled = sum(1 for c in changes if c["action"] == "scaled")
    frozen = sum(1 for c in changes if c["action"] == "frozen")
    unresolved = sum(1 for c in changes if c["action"] == "left_autosize")
    meta: dict[str, Any] = {
        "factors": validated,
        "changes": changes,
        "fields_scaled": scaled,
        "autosize_frozen": frozen,
        "autosize_unresolved": unresolved,
        "fields_patched": scaled + frozen,
        "flags": sorted(flags),
    }
    return text, meta


def apply_capacity_factors(
    src: Path,
    dest: Path,
    factors: Mapping[str, Any],
    *,
    resolver: Resolver | None = None,
) -> dict:
    """Scale equipment capacity/airflow fields by per-category factors."""
    src = Path(src)
    dest = Path(dest)
    text = src.read_text(encoding="utf-8", errors="replace")
    text, meta = scale_capacity_fields(text, factors, resolver=resolver)
    header = "! WattLab capacity patch: capacity_factors (conceptual sizing screen)\n"
    if "! WattLab capacity patch: capacity_factors" not in text:
        text = header + text
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    meta.update(
        {
            "patch": "capacity_factors",
            "out": str(dest),
            "ok": meta["fields_patched"] > 0,
        }
    )
    meta["flags"] = list(meta["flags"]) + [
        "conceptual_capacity_screen",
        "screening_only",
    ]
    return meta
