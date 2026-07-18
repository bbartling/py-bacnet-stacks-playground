"""Explicit deep-retrofit IDF patches for conceptual EnergyPlus screening."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping


_GLAZING_MATERIAL = "WattLab High Performance Simple Glazing"
_GLAZING_CONSTRUCTION = "WattLab High Performance Glazing"
_GLAZING_HEADER = "! WattLab deep retrofit: high_performance_glazing"


def _bounded(
    name: str,
    value: float,
    *,
    minimum: float,
    maximum: float,
    minimum_inclusive: bool = False,
) -> float:
    value = float(value)
    above_minimum = value >= minimum if minimum_inclusive else value > minimum
    if not above_minimum or value > maximum:
        lower = ">=" if minimum_inclusive else ">"
        raise ValueError(f"{name} must be {lower} {minimum} and <= {maximum}")
    return value


def _object_pattern(object_type: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?ms)^[ \t]*{re.escape(object_type)}[ \t]*,[ \t]*\r?\n"
        rf".*?;[^\r\n]*(?:\r?\n|$)"
    )


def _replace_commented_field(block: str, comment: str, value: str) -> tuple[str, int]:
    pattern = re.compile(
        rf"(?m)^([ \t]*)[^,!;\r\n]*([,;][ \t]*!-[ \t]*"
        rf"{re.escape(comment)}[ \t]*)(\r?\n|$)"
    )
    return pattern.subn(
        lambda match: f"{match.group(1)}{value}{match.group(2)}{match.group(3)}",
        block,
    )


def _patch_objects(
    text: str,
    object_type: str,
    replacements: Mapping[str, str],
) -> tuple[str, int, int]:
    pattern = _object_pattern(object_type)
    targets = list(pattern.finditer(text))
    if not targets:
        raise ValueError(f"No target {object_type} objects found")

    fields_patched = 0

    def replace_object(match: re.Match[str]) -> str:
        nonlocal fields_patched
        block = match.group(0)
        for comment, value in replacements.items():
            block, count = _replace_commented_field(block, comment, value)
            if count != 1:
                raise ValueError(
                    f"Expected one {comment!r} field in each target {object_type} object"
                )
            fields_patched += count
        return block

    patched = pattern.sub(replace_object, text)
    expected_fields = len(targets) * len(replacements)
    if fields_patched != expected_fields:
        raise ValueError(
            f"Expected {expected_fields} fields in target {object_type} objects; "
            f"patched {fields_patched}"
        )
    return patched, len(targets), fields_patched


def _patch_named_object(
    text: str,
    object_type: str,
    name: str,
    replacements: Mapping[str, str],
) -> tuple[str, int]:
    pattern = _object_pattern(object_type)
    targets_patched = 0

    def replace_object(match: re.Match[str]) -> str:
        nonlocal targets_patched
        block = match.group(0)
        name_pattern = re.compile(
            rf"(?mi)^[ \t]*{re.escape(name)}[ \t]*,[ \t]*"
            rf"!-[ \t]*Name[ \t]*$"
        )
        if not name_pattern.search(block):
            return block
        targets_patched += 1
        if targets_patched > 1:
            raise ValueError(f"Multiple target {object_type} objects named {name!r}")
        for comment, value in replacements.items():
            block, count = _replace_commented_field(block, comment, value)
            if count != 1:
                raise ValueError(
                    f"Expected one {comment!r} field in target {object_type} "
                    f"object {name!r}"
                )
        return block

    return pattern.sub(replace_object, text), targets_patched


def _with_header(text: str, header: str) -> str:
    marker = f"! WattLab deep retrofit: {header}"
    if marker in text:
        return text
    return f"{marker}\n{text}"


def _write(dest: Path, text: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")


def apply_high_performance_glazing(
    src: Path,
    dest: Path,
    *,
    u_factor: float = 1.4,
    shgc: float = 0.30,
    visible_transmittance: float = 0.50,
) -> dict:
    """Replace fenestration constructions with a simple-glazing envelope proxy."""
    u_factor = _bounded("u_factor", u_factor, minimum=0.0, maximum=10.0)
    shgc = _bounded(
        "shgc", shgc, minimum=0.0, maximum=1.0, minimum_inclusive=True
    )
    visible_transmittance = _bounded(
        "visible_transmittance",
        visible_transmittance,
        minimum=0.0,
        maximum=1.0,
        minimum_inclusive=True,
    )
    text = Path(src).read_text(encoding="utf-8", errors="replace")
    text, surfaces, _ = _patch_objects(
        text,
        "FenestrationSurface:Detailed",
        {"Construction Name": _GLAZING_CONSTRUCTION},
    )

    materials_added = 0
    materials_updated = 0
    constructions_added = 0
    text, existing_materials = _patch_named_object(
        text,
        "WindowMaterial:SimpleGlazingSystem",
        _GLAZING_MATERIAL,
        {
            "U-Factor {W/m2-K}": f"{u_factor:g}",
            "Solar Heat Gain Coefficient": f"{shgc:g}",
            "Visible Transmittance": f"{visible_transmittance:g}",
        },
    )
    if existing_materials:
        materials_updated = 1
    else:
        text = (
            text.rstrip()
            + "\n\n"
            + "WindowMaterial:SimpleGlazingSystem,\n"
            + f"    {_GLAZING_MATERIAL}, !- Name\n"
            + f"    {u_factor:g},                     !- U-Factor {{W/m2-K}}\n"
            + f"    {shgc:g},                     !- Solar Heat Gain Coefficient\n"
            + f"    {visible_transmittance:g};                     !- Visible Transmittance\n"
        )
        materials_added = 1
    if not re.search(
        rf"(?mi)^[ \t]*{re.escape(_GLAZING_CONSTRUCTION)}[ \t]*,[ \t]*"
        rf"!-?[ \t]*Name[ \t]*$",
        text,
    ):
        text = (
            text.rstrip()
            + "\n\n"
            + "Construction,\n"
            + f"    {_GLAZING_CONSTRUCTION}, !- Name\n"
            + f"    {_GLAZING_MATERIAL}; !- Outside Layer\n"
        )
        constructions_added = 1

    text = _with_header(text, "high_performance_glazing")
    _write(Path(dest), text)
    return {
        "patch": "high_performance_glazing",
        "u_factor": u_factor,
        "shgc": shgc,
        "visible_transmittance": visible_transmittance,
        "fenestration_surfaces_patched": surfaces,
        "glazing_materials_added": materials_added,
        "glazing_materials_updated": materials_updated,
        "glazing_materials_patched": materials_added + materials_updated,
        "constructions_added": constructions_added,
        "out": str(dest),
        "ok": True,
        "flags": ["conceptual_envelope_proxy", "screening_only"],
    }


def apply_condensing_boiler_efficiency(
    src: Path,
    dest: Path,
    *,
    efficiency: float = 0.95,
) -> dict:
    """Patch the existing hot-water boiler efficiency without changing its type."""
    efficiency = _bounded("efficiency", efficiency, minimum=0.0, maximum=1.0)
    text = Path(src).read_text(encoding="utf-8", errors="replace")
    text, boilers, fields = _patch_objects(
        text,
        "Boiler:HotWater",
        {"Nominal Thermal Efficiency": f"{efficiency:g}"},
    )
    text = _with_header(text, "condensing_boiler")
    _write(Path(dest), text)
    return {
        "patch": "condensing_boiler",
        "efficiency": efficiency,
        "boilers_patched": boilers,
        "fields_patched": fields,
        "out": str(dest),
        "ok": True,
        "flags": [
            "conceptual_major_equipment_replacement",
            "condensing_boiler_screening",
            "direct_efficiency_replacement",
        ],
    }


def apply_high_efficiency_chiller(
    src: Path,
    dest: Path,
    *,
    cop: float = 6.1,
) -> dict:
    """Patch nominal chiller COP while preserving the modeled condenser type."""
    cop = _bounded("cop", cop, minimum=0.0, maximum=20.0)
    text = Path(src).read_text(encoding="utf-8", errors="replace")
    text, chillers, fields = _patch_objects(
        text, "Chiller:Electric", {"Nominal COP {W/W}": f"{cop:g}"}
    )
    text = _with_header(text, "high_efficiency_chiller")
    _write(Path(dest), text)
    return {
        "patch": "high_efficiency_chiller",
        "cop": cop,
        "chillers_patched": chillers,
        "fields_patched": fields,
        "condenser_type_changed": False,
        "out": str(dest),
        "ok": True,
        "flags": [
            "conceptual_major_equipment_replacement",
            "high_efficiency_chiller_screening",
            "direct_efficiency_replacement",
        ],
    }


def apply_premium_fan_vfd(
    src: Path,
    dest: Path,
    *,
    total_efficiency: float = 0.75,
    motor_efficiency: float = 0.95,
    pressure_pa: float = 400.0,
    min_flow_fraction: float = 0.10,
) -> dict:
    """Patch variable-volume fan efficiency, pressure, and minimum flow."""
    total_efficiency = _bounded(
        "total_efficiency", total_efficiency, minimum=0.0, maximum=1.0
    )
    motor_efficiency = _bounded(
        "motor_efficiency", motor_efficiency, minimum=0.0, maximum=1.0
    )
    pressure_pa = _bounded("pressure_pa", pressure_pa, minimum=0.0, maximum=5000.0)
    min_flow_fraction = _bounded(
        "min_flow_fraction",
        min_flow_fraction,
        minimum=0.0,
        maximum=1.0,
        minimum_inclusive=True,
    )
    text = Path(src).read_text(encoding="utf-8", errors="replace")
    text, fans, fields = _patch_objects(
        text,
        "Fan:VariableVolume",
        {
            "Fan Total Efficiency": f"{total_efficiency:g}",
            "Motor Efficiency": f"{motor_efficiency:g}",
            "Pressure Rise {Pa}": f"{pressure_pa:g}",
            "Fan Power Minimum Flow Fraction": f"{min_flow_fraction:g}",
        },
    )
    text = _with_header(text, "premium_fan_vfd")
    _write(Path(dest), text)
    return {
        "patch": "premium_fan_vfd",
        "total_efficiency": total_efficiency,
        "motor_efficiency": motor_efficiency,
        "pressure_pa": pressure_pa,
        "min_flow_fraction": min_flow_fraction,
        "fans_patched": fans,
        "fields_patched": fields,
        "out": str(dest),
        "ok": True,
        "flags": ["premium_fan_vfd_screening", "direct_parameter_replacement"],
    }


def apply_air_to_water_heat_pump_surrogate(
    src: Path,
    dest: Path,
    *,
    cop: float = 2.8,
) -> dict:
    """Model an AWHP concept as an electric Boiler:HotWater efficiency surrogate."""
    cop = _bounded("cop", cop, minimum=0.0, maximum=20.0)
    text = Path(src).read_text(encoding="utf-8", errors="replace")
    text, boilers, fields = _patch_objects(
        text,
        "Boiler:HotWater",
        {
            "Fuel Type": "Electricity",
            "Nominal Thermal Efficiency": f"{cop:g}",
        },
    )
    text = _with_header(text, "awhp_surrogate")
    _write(Path(dest), text)
    return {
        "patch": "awhp_surrogate",
        "cop": cop,
        "boilers_patched": boilers,
        "fuel_types_patched": boilers,
        "efficiencies_patched": boilers,
        "fields_patched": fields,
        "description": (
            "Conceptual air-to-water heat-pump surrogate using an electric "
            "Boiler:HotWater object; not a construction-ready system model."
        ),
        "out": str(dest),
        "ok": True,
        "flags": [
            "conceptual_system_surrogate",
            "awhp_modeled_as_electric_boiler",
            "screening_only",
        ],
    }
