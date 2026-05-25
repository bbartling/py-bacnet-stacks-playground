"""BRICK class picklists for Rule Lab — derived from live registry + canonical model only."""

from __future__ import annotations

from typing import Any


def brick_scope_options(
    registry_points: list[dict[str, Any]],
    model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Open-FDD style: FDD rules target brick_type / fdd_input on points and equipment_type on equipment.
    No static HVAC preset lists — only classes present in telemetry registry or imported model.
    """
    point_classes: set[str] = set()
    equipment_classes: set[str] = set()

    for p in registry_points or []:
        bc = (p.get("brick_class") or "").strip()
        if bc:
            point_classes.add(bc)

    model = model or {}
    for p in model.get("points") or []:
        for key in ("brick_type", "fdd_input", "brick_class"):
            v = (p.get(key) or "").strip()
            if v:
                point_classes.add(v)
    for eq in model.get("equipment") or []:
        et = (eq.get("equipment_type") or eq.get("brick_type") or "").strip()
        if et:
            equipment_classes.add(et)

    equipment = sorted(equipment_classes)
    points = sorted(point_classes)
    return {
        "equipment": equipment,
        "points": points,
        "has_data": bool(equipment or points),
        "registry_point_count": len(registry_points or []),
    }
