"""Lightweight multi-site / building / equipment model (no RDF)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

EQUIPMENT_TYPES = (
    "AHU",
    "VAV",
    "CHW_PLANT",
    "BOILER",
    "HP",
    "WEATHER",
    "METER",
    "UNKNOWN",
)


@dataclass
class Point:
    point_id: str
    point_name: str
    column_name: str
    role: str
    unit: str = ""
    kind: str = "sensor"
    tags: dict[str, str] = field(default_factory=dict)
    source_file: str = ""
    source_table: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "point_id": self.point_id,
            "point_name": self.point_name,
            "column_name": self.column_name,
            "role": self.role,
            "unit": self.unit,
            "kind": self.kind,
            "tags": dict(self.tags),
            "source_file": self.source_file,
            "source_table": self.source_table,
        }


@dataclass
class Equipment:
    equipment_id: str
    equipment_name: str
    equipment_type: str
    site_id: str
    building_id: str
    source_id: str = ""
    roles: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "equipment_id": self.equipment_id,
            "equipment_name": self.equipment_name,
            "equipment_type": self.equipment_type,
            "site_id": self.site_id,
            "building_id": self.building_id,
            "source_id": self.source_id,
            "roles": dict(self.roles),
        }


@dataclass
class Building:
    building_id: str
    building_name: str
    site_id: str
    timezone: str = "UTC"
    equipment: dict[str, Equipment] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "building_id": self.building_id,
            "building_name": self.building_name,
            "site_id": self.site_id,
            "timezone": self.timezone,
            "equipment": {k: v.to_dict() for k, v in self.equipment.items()},
        }


@dataclass
class Site:
    site_id: str
    site_name: str
    timezone: str = "UTC"
    buildings: dict[str, Building] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "site_id": self.site_id,
            "site_name": self.site_name,
            "timezone": self.timezone,
            "buildings": {k: v.to_dict() for k, v in self.buildings.items()},
        }

    def all_equipment(self) -> list[Equipment]:
        out: list[Equipment] = []
        for b in self.buildings.values():
            out.extend(b.equipment.values())
        return out


def sites_to_yaml_dict(sites: dict[str, Site]) -> dict[str, Any]:
    return {"sites": {sid: s.to_dict() for sid, s in sites.items()}}


def equipment_type_from_id(equipment_id: str) -> str:
    u = equipment_id.upper().replace("\\", "/")
    if "WEATHER" in u:
        return "WEATHER"
    if "VAV" in u:
        return "VAV"
    if u.startswith("AHU") or "/AHU" in u:
        return "AHU"
    if "CHILLER" in u or u.startswith("CHW"):
        return "CHW_PLANT"
    if "BOILER" in u:
        return "BOILER"
    if "HEAT" in u and "PUMP" in u:
        return "HP"
    if "METER" in u:
        return "METER"
    return "UNKNOWN"
