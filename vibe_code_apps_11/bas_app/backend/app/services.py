"""Read-only demo query helpers for the BAS backend."""

from __future__ import annotations

from functools import lru_cache

from .demo_data import (
    build_demo_site,
    equipment_detail,
    find_equipment,
    find_point,
    find_points,
    point_detail,
    point_list,
    schedule_catalog,
    site_navigation,
    site_to_dict,
)
from .commands import get_command_state


@lru_cache(maxsize=1)
def get_demo_site():
    return build_demo_site()


def read_demo_site() -> dict[str, object]:
    return site_to_dict(get_demo_site())


def read_navigation() -> dict[str, object]:
    return site_navigation(get_demo_site())


def read_equipment(equipment_id: str) -> dict[str, object] | None:
    equipment = find_equipment(get_demo_site(), equipment_id)
    if equipment is None:
        return None
    return equipment_detail(equipment)


def read_equipment_points(equipment_id: str) -> list[dict[str, object]] | None:
    points = find_points(get_demo_site(), equipment_id)
    if points is None:
        return None
    return point_list(points)


def read_point(point_id: str) -> dict[str, object] | None:
    match = find_point(get_demo_site(), point_id)
    if match is None:
        return None
    equipment, point = match
    return point_detail(equipment, point, command_state=get_command_state(point.id))


def read_schedules() -> dict[str, object]:
    return schedule_catalog(get_demo_site())
