"""Parse IDF text into an energy-modeler dashboard (Pydantic)."""
from __future__ import annotations

import re
from pathlib import Path

from .idf_geometry import _polygon_area_m2, parse_idf_geometry
from .models import CoilRating, EnvelopeMetrics, IdfDashboard, SimulationControlFlags, _yes_no

_FT2_PER_M2 = 10.76391041671
_W_PER_TON = 3516.8525

_OBJECT_RE = re.compile(
    r"(?ms)^[ \t]*([A-Za-z][A-Za-z0-9:.-]*)[ \t]*,[ \t]*(?:\r?\n)?(.*?)[ \t]*;[^\r\n]*(?:\r?\n|$)"
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


def _is_autosize(token: str) -> bool:
    return token.strip().lower() == "autosize"


def _float_or_none(token: str | None) -> float | None:
    if token is None or _is_autosize(token) or token in {"", "-"}:
        return None
    try:
        return float(token)
    except ValueError:
        return None


def inspect_idf(text_or_path: str | Path, *, source_name: str | None = None) -> IdfDashboard:
    if isinstance(text_or_path, Path) or (
        isinstance(text_or_path, str) and len(text_or_path) < 400 and Path(text_or_path).is_file()
    ):
        path = Path(text_or_path)
        text = path.read_text(encoding="utf-8", errors="replace")
        source_name = source_name or path.name
    else:
        text = str(text_or_path)
        source_name = source_name or "uploaded.idf"

    geom = parse_idf_geometry(text)
    env_ratios = geom.envelope_ratios()
    floor_m2 = 0.0
    for surf in geom.surfaces:
        if (surf.surface_type or "").upper() == "FLOOR":
            floor_m2 += _polygon_area_m2(surf.vertices)
    bb = geom.summary().get("bbox_ft") or {}
    envelope = EnvelopeMetrics(
        n_surfaces=len(geom.surfaces),
        n_zones=len(geom.zone_names),
        n_fenestration=sum(1 for s in geom.surfaces if s.is_fenestration),
        floor_m2=round(floor_m2, 2),
        floor_ft2=round(floor_m2 * _FT2_PER_M2, 0),
        wall_m2=float(env_ratios["wall_area_m2"]),
        window_m2=float(env_ratios["window_area_m2"]),
        roof_m2=float(env_ratios["roof_area_m2"]),
        wwr=env_ratios.get("wwr"),
        wwr_pct=env_ratios.get("wwr_pct"),
        bbox_ft_dx=bb.get("dx"),
        bbox_ft_dy=bb.get("dy"),
        bbox_ft_dz=bb.get("dz"),
    )

    version = None
    building_name = None
    north_axis = None
    timestep = None
    location_name = None
    latitude = None
    longitude = None
    elevation_m = None
    zone_names: list[str] = []
    equipment_types: list[str] = []
    sim = SimulationControlFlags()
    coils: list[CoilRating] = []
    autosized_field_count = 0
    cooling_w = None
    heating_w = None

    for match in _OBJECT_RE.finditer(text):
        obj = match.group(1).strip()
        fields = _fields(match.group(2))
        autosized_field_count += sum(1 for f in fields if _is_autosize(f))
        key = obj.lower()
        if key == "version" and fields:
            version = fields[0]
        elif key == "timestep" and fields:
            timestep = int(float(fields[0]))
        elif key == "building" and fields:
            building_name = fields[0]
            if len(fields) > 1:
                north_axis = _float_or_none(fields[1])
        elif key == "site:location" and fields:
            location_name = fields[0]
            if len(fields) > 1:
                latitude = _float_or_none(fields[1])
            if len(fields) > 2:
                longitude = _float_or_none(fields[2])
            if len(fields) > 4:
                elevation_m = _float_or_none(fields[4])
        elif key == "simulationcontrol" and len(fields) >= 6:
            sim = SimulationControlFlags(
                zone_sizing=_yes_no(fields[0]),
                system_sizing=_yes_no(fields[1]),
                plant_sizing=_yes_no(fields[2]),
                hvac_sizing_simulation=_yes_no(fields[5]),
            )
        elif key == "zone" and fields:
            zone_names.append(fields[0])
        elif key.startswith("zonehvac:") and fields:
            equipment_types.append(obj)
        elif key.startswith("coil:cooling"):
            rated = _float_or_none(fields[2] if len(fields) > 2 else None)
            cop = _float_or_none(fields[4] if len(fields) > 4 else None)
            auto = any(_is_autosize(f) for f in fields[:6])
            coils.append(
                CoilRating(
                    name=fields[0] if fields else obj,
                    object_type=obj,
                    rated_w=rated,
                    rated_cop=cop,
                    autosized=auto or rated is None,
                )
            )
            if rated is not None:
                cooling_w = rated if cooling_w is None else cooling_w + rated
        elif key.startswith("coil:heating:dx"):
            rated = _float_or_none(fields[2] if len(fields) > 2 else None)
            cop = _float_or_none(fields[3] if len(fields) > 3 else None)
            auto = any(_is_autosize(f) for f in fields[:5])
            coils.append(
                CoilRating(
                    name=fields[0] if fields else obj,
                    object_type=obj,
                    rated_w=rated,
                    rated_cop=cop,
                    autosized=auto or rated is None,
                )
            )
            if rated is not None:
                heating_w = rated if heating_w is None else heating_w + rated

    zone_names = sorted(set(zone_names) | set(geom.zone_names))
    hvac_autosize = sim.any_autosize_control or any(c.autosized for c in coils) or autosized_field_count > 0
    cooling_tons = round(cooling_w / _W_PER_TON, 2) if cooling_w else None
    return IdfDashboard(
        source_name=source_name,
        version=version,
        building_name=building_name,
        timestep=timestep,
        north_axis_deg=north_axis,
        location_name=location_name,
        latitude=latitude,
        longitude=longitude,
        elevation_m=elevation_m,
        zone_names=zone_names,
        equipment_types=sorted(set(equipment_types)),
        simulation_control=sim,
        envelope=envelope,
        coils=coils,
        autosized_field_count=autosized_field_count,
        hvac_autosize=hvac_autosize,
        cooling_capacity_w=cooling_w,
        heating_capacity_w=heating_w,
        cooling_tons=cooling_tons,
    )
