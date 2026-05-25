"""BRICK time-series refs (mirror ingest_lambda/brick_timeseries.py for API responses)."""

from __future__ import annotations

import json
from typing import Any

BRICK_CONTEXT = "https://brickschema.org/schema/Brick#"
EXT_NS = "https://vibe12.local/ext#"


def brick_point_entity_id(site_id: str, building_id: str, series_id: str) -> str:
    safe = series_id.replace("#", "/")
    return f"brick:{site_id}/{building_id}/point/{safe}"


def brick_equipment_entity_id(site_id: str, building_id: str, system_id: str) -> str:
    return f"brick:{site_id}/{building_id}/equipment/{system_id}"


def brick_timeseries_ref(
    *,
    site_id: str,
    building_id: str,
    system_id: str,
    point_id: str,
    series_id: str,
    brick_class: str = "",
    brick_tag: str = "",
    unit: str = "",
) -> dict[str, Any]:
    entity_id = brick_point_entity_id(site_id, building_id, series_id)
    equipment_id = brick_equipment_entity_id(site_id, building_id, system_id)
    return {
        "@context": {"brick": BRICK_CONTEXT, "ext": EXT_NS},
        "entity_id": entity_id,
        "equipment_id": equipment_id,
        "brick_class": brick_class or "Point",
        "brick_tag": brick_tag,
        "series_id": series_id,
        "external_ref": series_id,
        "hasUnit": unit,
        "dynamodb": {
            "table_key": {"device_id": series_id, "sort_key": "ts_ms"},
            "building_scope": f"{site_id}#{building_id}",
        },
        "mqtt_topic": (
            f"vibe12/{site_id}/{building_id}/{system_id}/{point_id}/telemetry"
        ),
    }


def parse_stored_ref(raw: Any) -> dict[str, Any] | None:
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return None


def registry_entry_from_row(row: dict[str, Any]) -> dict[str, Any]:
    ref = brick_timeseries_ref(
        site_id=row["site_id"],
        building_id=row["building_id"],
        system_id=row.get("system_id") or "",
        point_id=row["point_id"],
        series_id=row["series_id"],
        brick_class=row.get("brick_class", ""),
        brick_tag=row.get("brick_tag", ""),
    )
    ref["hasUnit"] = row.get("unit", "")
    return {
        "series_id": row["series_id"],
        "site_id": row["site_id"],
        "building_id": row["building_id"],
        "system_id": row.get("system_id") or "",
        "point_id": row["point_id"],
        "unit": row.get("unit", ""),
        "brick_class": row.get("brick_class", ""),
        "brick_tag": row.get("brick_tag", ""),
        "object_name": row.get("object_name", ""),
        "source": row.get("source", "bacnet"),
        "equipment_type": row.get("equipment_type") or "HVAC_Equipment",
        "external_ref": row["series_id"],
        "brick_timeseries_ref": ref,
        "entity_id": ref["entity_id"],
    }
