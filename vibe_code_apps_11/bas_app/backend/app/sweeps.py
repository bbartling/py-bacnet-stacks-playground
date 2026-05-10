"""Tiny demo data sweep helpers for the BAS backend."""

from __future__ import annotations

from .services import get_demo_site, read_equipment, read_equipment_points, read_point


def read_demo_data_sweep() -> dict[str, object]:
    """Return a compact happy-path summary from site through point detail."""

    site = get_demo_site()
    building = site.buildings[0]
    floor = building.floors[0]
    equipment = floor.equipment[0]
    points = read_equipment_points(equipment.id) or []
    point_id = "pt-sa-sp" if any(point["id"] == "pt-sa-sp" for point in points) else points[0]["id"]
    point = read_point(point_id)

    return {
        "site": {
            "id": site.id,
            "name": site.name,
        },
        "building": {
            "id": building.id,
            "name": building.name,
        },
        "floor": {
            "id": floor.id,
            "name": floor.name,
        },
        "equipment": read_equipment(equipment.id),
        "points": {
            "ids": [point_item["id"] for point_item in points],
            "count": len(points),
        },
        "point_detail": {
            "id": point["id"] if point else None,
            "equipment_id": point["equipment"]["id"] if point else None,
            "source_protocol": point["source_protocol"] if point else None,
            "source_address": point["source_address"] if point else None,
        },
    }
