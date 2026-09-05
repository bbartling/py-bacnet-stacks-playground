"""Compatibility preflight for uploaded / foreign IDFs (Pydantic)."""
from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .idf_geometry import parse_idf_geometry
from .idf_inspect import inspect_idf

_OBJECT_RE = re.compile(
    r"(?ms)^[ \t]*([A-Za-z][A-Za-z0-9:.-]*)[ \t]*,[ \t]*(?:\r?\n)?(.*?)[ \t]*;[^\r\n]*(?:\r?\n|$)"
)
_SCHEDULE_NAME_RE = re.compile(
    r"(?ims)^\s*Schedule:Compact\s*,\s*([^,;\n]+)",
)
_METER_RE = re.compile(
    r"(?ims)Output:Meter\s*,\s*Electricity:Facility\s*,\s*Timestep\s*;",
)
_ZONE_TEMP_RE = re.compile(
    r"(?ims)Output:Variable\s*,\s*[^,]+,\s*Zone Mean Air Temperature\s*,\s*Timestep\s*;",
)


def _fields(body: str) -> list[str]:
    tokens: list[str] = []
    for line in body.splitlines():
        cleaned = line.split("!-")[0].split("!")[0].strip()
        if not cleaned:
            continue
        for chunk in cleaned.split(","):
            t = chunk.strip().rstrip(";").strip()
            if t:
                tokens.append(t)
    return tokens


class IdfPreflight(BaseModel):
    """Traffic-light compatibility report for Studio visualize / simulate paths."""

    model_config = ConfigDict(extra="forbid")

    source_name: str
    n_zones: int = 0
    has_building_surfaces: bool = False
    has_heat_setpoint_schedule: bool = False
    has_cool_setpoint_schedule: bool = False
    has_facility_meter_timestep: bool = False
    has_zone_temp_timestep: bool = False
    declared_timestep: int | None = None
    can_visualize: bool = False
    can_simulate: bool = False
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def preflight_idf(text_or_path: str | Path, *, source_name: str | None = None) -> IdfPreflight:
    if isinstance(text_or_path, Path) or (
        isinstance(text_or_path, str) and len(text_or_path) < 400 and Path(text_or_path).is_file()
    ):
        path = Path(text_or_path)
        text = path.read_text(encoding="utf-8", errors="replace")
        source_name = source_name or path.name
    else:
        text = str(text_or_path)
        source_name = source_name or "uploaded.idf"

    dashboard = inspect_idf(text, source_name=source_name)
    geom = parse_idf_geometry(text)

    schedule_names: set[str] = set()
    for match in _SCHEDULE_NAME_RE.finditer(text):
        schedule_names.add(match.group(1).strip().upper())

    # Also walk Schedule:Compact via object regex for robustness.
    declared_timestep = dashboard.timestep
    for match in _OBJECT_RE.finditer(text):
        obj = match.group(1).strip()
        fields = _fields(match.group(2))
        key = obj.lower()
        if key == "schedule:compact" and fields:
            schedule_names.add(fields[0].upper())
        if key == "timestep" and fields and declared_timestep is None:
            try:
                declared_timestep = int(float(fields[0]))
            except ValueError:
                declared_timestep = None

    has_heat = "HEAT SETPOINT" in schedule_names
    has_cool = "COOL SETPOINT" in schedule_names
    has_surfaces = len(geom.surfaces) > 0 and any(not s.is_fenestration for s in geom.surfaces)
    has_meter = bool(_METER_RE.search(text))
    has_zone_temp = bool(_ZONE_TEMP_RE.search(text))
    n_zones = max(len(dashboard.zone_names), len(geom.zone_names))

    blockers: list[str] = []
    warnings: list[str] = []

    if not has_surfaces:
        blockers.append("missing BuildingSurface:Detailed (cannot visualize massing)")
    if not has_heat:
        blockers.append("missing Schedule:Compact named HEAT SETPOINT (required for residential runner)")
    if not has_cool:
        blockers.append("missing Schedule:Compact named COOL SETPOINT (required for residential runner)")
    if not has_meter:
        blockers.append("missing Output:Meter,Electricity:Facility,Timestep (CSV parse will fail)")
    if not has_zone_temp:
        blockers.append("missing Output:Variable Zone Mean Air Temperature at Timestep")
    if declared_timestep is None:
        warnings.append("Timestep not declared; residential runner assumes Timestep=12 (5-min)")
    elif declared_timestep != 12:
        warnings.append(
            f"declared Timestep={declared_timestep}; residential runner assumes Timestep=12 "
            "(kW math / 288 resampling may be wrong)"
        )
    if n_zones == 0:
        warnings.append("no Zone objects found")
    elif n_zones > 1:
        warnings.append(f"multi-zone IDF ({n_zones} zones); Studio twin uses a single-zone fixture path")

    can_visualize = has_surfaces
    can_simulate = has_heat and has_cool and has_meter and has_zone_temp

    return IdfPreflight(
        source_name=source_name,
        n_zones=n_zones,
        has_building_surfaces=has_surfaces,
        has_heat_setpoint_schedule=has_heat,
        has_cool_setpoint_schedule=has_cool,
        has_facility_meter_timestep=has_meter,
        has_zone_temp_timestep=has_zone_temp,
        declared_timestep=declared_timestep,
        can_visualize=can_visualize,
        can_simulate=can_simulate,
        blockers=blockers,
        warnings=warnings,
    )


__all__ = ["IdfPreflight", "preflight_idf"]
