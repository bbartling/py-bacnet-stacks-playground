"""Seeded demo BAS data and a tiny simulator-backed snapshot."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class Point:
    id: str
    name: str
    display_name: str
    point_type: str
    units: str
    present_value: Any
    is_commandable: bool
    is_trended: bool
    is_alarmable: bool
    last_updated: str


@dataclass(slots=True)
class Equipment:
    id: str
    name: str
    equipment_type: str
    description: str
    serving_area: str
    status: str
    communication_status: str
    alarm_status: str
    points: list[Point] = field(default_factory=list)


@dataclass(slots=True)
class Floor:
    id: str
    name: str
    level: int
    equipment: list[Equipment] = field(default_factory=list)


@dataclass(slots=True)
class Building:
    id: str
    name: str
    description: str
    building_number: str
    floor_count: int
    floors: list[Floor] = field(default_factory=list)


@dataclass(slots=True)
class Site:
    id: str
    name: str
    description: str
    address: str
    timezone: str
    buildings: list[Building] = field(default_factory=list)


@dataclass(slots=True)
class Schedule:
    id: str
    name: str
    category: str
    program_context: str
    equipment_id: str | None
    point_id: str | None
    weekly_schedule: dict[str, Any]
    exception_schedule: list[dict[str, Any]]
    effective_date: str
    timezone: str
    enabled: bool


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_demo_site() -> Site:
    """Return a seeded demo site with multiple equipment types and trended points."""

    now = _utc_now()

    ahu = Equipment(
        id="eq-ahu-1",
        name="AHU-1",
        equipment_type="AHU",
        description="Central air handling unit serving the office wing.",
        serving_area="Level 1 offices",
        status="normal",
        communication_status="online",
        alarm_status="clear",
        points=[
            Point(
                id="pt-sat",
                name="ahu1_sat",
                display_name="Supply Air Temp",
                point_type="analog_input",
                units="degF",
                present_value=54.2,
                is_commandable=False,
                is_trended=True,
                is_alarmable=True,
                last_updated=now,
            ),
            Point(
                id="pt-mat",
                name="ahu1_mat",
                display_name="Mixed Air Temp",
                point_type="analog_input",
                units="degF",
                present_value=61.7,
                is_commandable=False,
                is_trended=True,
                is_alarmable=True,
                last_updated=now,
            ),
            Point(
                id="pt-ra",
                name="ahu1_ra",
                display_name="Return Air Temp",
                point_type="analog_input",
                units="degF",
                present_value=72.1,
                is_commandable=False,
                is_trended=True,
                is_alarmable=True,
                last_updated=now,
            ),
            Point(
                id="pt-sa-sp",
                name="ahu1_sa_sp",
                display_name="Supply Air Setpoint",
                point_type="analog_value",
                units="degF",
                present_value=55.0,
                is_commandable=True,
                is_trended=True,
                is_alarmable=False,
                last_updated=now,
            ),
            Point(
                id="pt-damper",
                name="ahu1_oa_damper",
                display_name="Outside Air Damper",
                point_type="analog_output",
                units="pct",
                present_value=22.0,
                is_commandable=True,
                is_trended=True,
                is_alarmable=False,
                last_updated=now,
            ),
            Point(
                id="pt-fan",
                name="ahu1_supply_fan",
                display_name="Supply Fan Status",
                point_type="binary_output",
                units="state",
                present_value="On",
                is_commandable=True,
                is_trended=True,
                is_alarmable=True,
                last_updated=now,
            ),
        ],
    )

    vav = Equipment(
        id="eq-vav-1",
        name="VAV-1",
        equipment_type="VAV",
        description="Representative terminal unit for the north offices.",
        serving_area="North office zone",
        status="normal",
        communication_status="online",
        alarm_status="clear",
        points=[
            Point(
                id="pt-zone-temp",
                name="vav1_zone_temp",
                display_name="Zone Temp",
                point_type="analog_input",
                units="degF",
                present_value=71.4,
                is_commandable=False,
                is_trended=True,
                is_alarmable=True,
                last_updated=now,
            ),
            Point(
                id="pt-zone-sp",
                name="vav1_zone_sp",
                display_name="Zone Setpoint",
                point_type="analog_value",
                units="degF",
                present_value=72.0,
                is_commandable=True,
                is_trended=True,
                is_alarmable=False,
                last_updated=now,
            ),
            Point(
                id="pt-box-damper",
                name="vav1_damper",
                display_name="Damper Position",
                point_type="analog_output",
                units="pct",
                present_value=38.5,
                is_commandable=True,
                is_trended=True,
                is_alarmable=False,
                last_updated=now,
            ),
            Point(
                id="pt-reheat",
                name="vav1_reheat",
                display_name="Reheat Command",
                point_type="binary_output",
                units="state",
                present_value="Off",
                is_commandable=True,
                is_trended=True,
                is_alarmable=True,
                last_updated=now,
            ),
        ],
    )

    lighting = Equipment(
        id="eq-light-1",
        name="LGT-PNL-1",
        equipment_type="Lighting Panel",
        description="Ancillary lighting panel for the lobby and corridors.",
        serving_area="Lobby and first-floor corridors",
        status="normal",
        communication_status="online",
        alarm_status="clear",
        points=[
            Point(
                id="pt-light-enable",
                name="lgtpnl1_enable",
                display_name="Panel Enable",
                point_type="binary_value",
                units="state",
                present_value="On",
                is_commandable=True,
                is_trended=True,
                is_alarmable=True,
                last_updated=now,
            ),
            Point(
                id="pt-light-mode",
                name="lgtpnl1_mode",
                display_name="Schedule Mode",
                point_type="multistate_value",
                units="mode",
                present_value="Occupied",
                is_commandable=True,
                is_trended=True,
                is_alarmable=False,
                last_updated=now,
            ),
            Point(
                id="pt-light-load",
                name="lgtpnl1_load",
                display_name="Panel Load",
                point_type="analog_input",
                units="kw",
                present_value=11.8,
                is_commandable=False,
                is_trended=True,
                is_alarmable=True,
                last_updated=now,
            ),
            Point(
                id="pt-light-override",
                name="lgtpnl1_override",
                display_name="Local Override",
                point_type="binary_input",
                units="state",
                present_value="Off",
                is_commandable=False,
                is_trended=False,
                is_alarmable=True,
                last_updated=now,
            ),
        ],
    )

    floor = Floor(id="floor-1", name="Level 1", level=1, equipment=[ahu, vav, lighting])
    building = Building(
        id="bldg-1",
        name="Central Plant & Office Wing",
        description="Demo building for BAS supervisory head-end workflows.",
        building_number="01",
        floor_count=1,
        floors=[floor],
    )

    return Site(
        id="site-1",
        name="GL36 Demo Campus",
        description="Seeded BAS demo site with simulator-backed live values.",
        address="100 Main St, Demo City",
        timezone="America/Denver",
        buildings=[building],
    )


def _build_demo_schedules() -> list[Schedule]:
    return [
        Schedule(
            id="sch-air-side-occupancy",
            name="Air-Side Occupancy",
            category="air_side_occupancy",
            program_context="Office air-side occupied/unoccupied window",
            equipment_id="eq-ahu-1",
            point_id="pt-sa-sp",
            weekly_schedule={
                "mon_fri": [{"start": "06:00", "end": "18:00", "mode": "occupied"}],
                "sat": [{"start": "08:00", "end": "12:00", "mode": "occupied_cleaning"}],
                "sun": [{"start": "00:00", "end": "00:00", "mode": "unoccupied"}],
            },
            exception_schedule=[
                {"date": "2026-05-25", "mode": "holiday"},
            ],
            effective_date="2026-05-01",
            timezone="America/Denver",
            enabled=True,
        ),
        Schedule(
            id="sch-ventilation-doas",
            name="Ventilation / DOAS",
            category="ventilation_doas",
            program_context="Ventilation lead for occupied outside-air purge",
            equipment_id="eq-ahu-1",
            point_id="pt-damper",
            weekly_schedule={
                "mon_fri": [{"start": "05:30", "end": "19:00", "mode": "ventilation"}],
                "sat_sun": [{"start": "07:00", "end": "11:00", "mode": "reduced_ventilation"}],
            },
            exception_schedule=[
                {"date": "2026-06-01", "mode": "maintenance"},
            ],
            effective_date="2026-05-01",
            timezone="America/Denver",
            enabled=True,
        ),
        Schedule(
            id="sch-terminal-zone-setback",
            name="Terminal Zone Setback",
            category="terminal_zone_setback",
            program_context="Representative zone setpoint window for the office wing",
            equipment_id="eq-vav-1",
            point_id="pt-zone-sp",
            weekly_schedule={
                "mon_fri": [{"start": "06:00", "end": "18:00", "mode": "occupied"}],
                "overnight": [{"start": "18:00", "end": "06:00", "mode": "setback"}],
            },
            exception_schedule=[
                {"date": "2026-05-29", "mode": "after_hours_event"},
            ],
            effective_date="2026-05-01",
            timezone="America/Denver",
            enabled=True,
        ),
        Schedule(
            id="sch-lighting-ancillary",
            name="Lighting Ancillary",
            category="lighting_ancillary",
            program_context="Lobby and corridor lighting panel schedule",
            equipment_id="eq-light-1",
            point_id="pt-light-enable",
            weekly_schedule={
                "mon_sun": [{"start": "05:00", "end": "23:00", "mode": "lighting_occupied"}],
            },
            exception_schedule=[
                {"date": "2026-05-24", "mode": "holiday_shutdown"},
            ],
            effective_date="2026-05-01",
            timezone="America/Denver",
            enabled=True,
        ),
    ]


_DEMO_SCHEDULES = _build_demo_schedules()


def site_to_dict(site: Site) -> dict[str, Any]:
    return asdict(site)


def iter_equipment(site: Site) -> list[Equipment]:
    equipment: list[Equipment] = []
    for building in site.buildings:
        for floor in building.floors:
            equipment.extend(floor.equipment)
    return equipment


def find_equipment(site: Site, equipment_id: str) -> Equipment | None:
    for equipment in iter_equipment(site):
        if equipment.id == equipment_id:
            return equipment
    return None


def find_points(site: Site, equipment_id: str) -> list[Point] | None:
    equipment = find_equipment(site, equipment_id)
    if equipment is None:
        return None
    return equipment.points


def site_navigation(site: Site) -> dict[str, Any]:
    buildings: list[dict[str, Any]] = []
    equipment_count = 0
    point_count = 0

    for building in site.buildings:
        building_dict: dict[str, Any] = {
            "id": building.id,
            "name": building.name,
            "description": building.description,
            "building_number": building.building_number,
            "floor_count": building.floor_count,
            "floors": [],
        }
        for floor in building.floors:
            floor_dict: dict[str, Any] = {
                "id": floor.id,
                "name": floor.name,
                "level": floor.level,
                "equipment": [],
            }
            for equipment in floor.equipment:
                floor_dict["equipment"].append(
                    {
                        "id": equipment.id,
                        "name": equipment.name,
                        "equipment_type": equipment.equipment_type,
                        "status": equipment.status,
                        "communication_status": equipment.communication_status,
                        "alarm_status": equipment.alarm_status,
                        "point_count": len(equipment.points),
                    }
                )
                equipment_count += 1
                point_count += len(equipment.points)
            building_dict["floors"].append(floor_dict)
        buildings.append(building_dict)

    return {
        "site": {
            "id": site.id,
            "name": site.name,
            "description": site.description,
            "address": site.address,
            "timezone": site.timezone,
        },
        "summary": {
            "building_count": len(site.buildings),
            "equipment_count": equipment_count,
            "point_count": point_count,
            "trended_point_count": sum(
                1 for equipment in iter_equipment(site) for point in equipment.points if point.is_trended
            ),
        },
        "buildings": buildings,
    }


def equipment_detail(equipment: Equipment) -> dict[str, Any]:
    return {
        "id": equipment.id,
        "name": equipment.name,
        "equipment_type": equipment.equipment_type,
        "description": equipment.description,
        "serving_area": equipment.serving_area,
        "status": equipment.status,
        "communication_status": equipment.communication_status,
        "alarm_status": equipment.alarm_status,
        "point_count": len(equipment.points),
    }


def find_point(site: Site, point_id: str) -> tuple[Equipment, Point] | None:
    for equipment in iter_equipment(site):
        for point in equipment.points:
            if point.id == point_id:
                return equipment, point
    return None


def point_detail(
    equipment: Equipment,
    point: Point,
    command_state: Any | None = None,
) -> dict[str, Any]:
    command_roles = ["Admin", "Engineer", "Operator"] if point.is_commandable else []
    is_overridden = command_state is not None
    present_value = command_state.commanded_value if command_state is not None else point.present_value
    return {
        "id": point.id,
        "name": point.name,
        "display_name": point.display_name,
        "description": "",
        "equipment": {
            "id": equipment.id,
            "name": equipment.name,
            "equipment_type": equipment.equipment_type,
        },
        "point_type": point.point_type,
        "object_type": point.point_type,
        "object_instance": point.id,
        "units": point.units,
        "present_value": present_value,
        "status_flags": ["overridden"] if is_overridden else [],
        "is_commandable": point.is_commandable,
        "is_trended": point.is_trended,
        "is_alarmable": point.is_alarmable,
        "is_commanded": is_overridden,
        "is_overridden": is_overridden,
        "commanded_value": command_state.commanded_value if command_state is not None else None,
        "commanded_by": command_state.commanded_by if command_state is not None else None,
        "command_timestamp": command_state.command_timestamp if command_state is not None else None,
        "original_value": command_state.original_value if command_state is not None else None,
        "relinquish_default": command_state.original_value if command_state is not None else None,
        "command_reason": command_state.reason if command_state is not None else None,
        "command_roles": command_roles,
        "permission_summary": {
            "read_only": "View only",
            "operator": "Can command" if point.is_commandable else "View only",
            "engineer": "Can command" if point.is_commandable else "View only",
            "admin": "Can command" if point.is_commandable else "View only",
        },
        "last_updated": point.last_updated,
        "source_protocol": "simulator",
        "source_address": f"sim://{equipment.id}/{point.id}",
        "writable_priority": 16 if point.is_commandable else None,
    }


def point_list(points: list[Point]) -> list[dict[str, Any]]:
    return [asdict(point) for point in points]


def schedule_list() -> list[dict[str, Any]]:
    return [asdict(schedule) for schedule in _DEMO_SCHEDULES]


def schedule_catalog(site: Site) -> dict[str, Any]:
    schedules = schedule_list()
    category_labels = {
        "air_side_occupancy": "Air-side occupancy",
        "ventilation_doas": "Ventilation / DOAS",
        "terminal_zone_setback": "Terminal zone setback",
        "lighting_ancillary": "Lighting ancillary",
    }
    category_counts: dict[str, int] = {}
    for schedule in schedules:
        category = str(schedule["category"])
        category_counts[category] = category_counts.get(category, 0) + 1

    category_buckets = [
        {
            "category": category,
            "label": category_labels.get(category, category.replace("_", " ").title()),
            "count": category_counts[category],
        }
        for category in category_labels
        if category in category_counts
    ]

    return {
        "site": {
            "id": site.id,
            "name": site.name,
            "timezone": site.timezone,
        },
        "summary": {
            "schedule_count": len(schedules),
            "category_buckets": category_buckets,
        },
        "items": schedules,
    }
