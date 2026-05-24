"""MQTT topic parsing and DynamoDB key helpers (shared ingest + web)."""

from __future__ import annotations

import re
from typing import Any

TOPIC_PREFIX = "vibe12"
TOPIC_RE = re.compile(
    rf"^{TOPIC_PREFIX}/(?P<site>[^/]+)/(?P<building>[^/]+)/"
    r"(?P<system>[^/]+)/(?P<point>[^/]+)/telemetry$"
)

BRICK_GRAPH_TS = -10
POINT_REGISTRY_TS = -11
BRICK_TTL_TS = -12
CANONICAL_MODEL_TS = -13
BRICK_FDD_SUMMARY_TS = -14


def parse_mqtt_topic(topic: str | None) -> dict[str, str] | None:
    if not topic:
        return None
    m = TOPIC_RE.match(topic.strip())
    if not m:
        return None
    return dict(m.groupdict())


def building_scope(site_id: str, building_id: str) -> str:
    return f"{site_id}#{building_id}"


def scope_sort_key(system_id: str, point_id: str, ts_ms: int) -> str:
    return f"{system_id}#{point_id}#{ts_ms}"


def meta_device_id(site_id: str, building_id: str) -> str:
    return f"meta#{site_id}#{building_id}"


def is_legacy_ds18b20(body: dict[str, Any]) -> bool:
    return body.get("source", "ds18b20") == "ds18b20" and "degC" in body and "degF" in body


def is_bacnet_telemetry(body: dict[str, Any]) -> bool:
    return body.get("source") == "bacnet" and bool(body.get("series_id"))


def is_legacy_series_id(series_id: str, default_device: str) -> bool:
    return series_id == default_device or "#" not in series_id


def series_row_from_bacnet(body: dict[str, Any], topic_meta: dict[str, str] | None) -> dict[str, Any]:
    site_id = body.get("site_id") or (topic_meta or {}).get("site", "")
    building_id = body.get("building_id") or (topic_meta or {}).get("building", "")
    system_id = body.get("system_id") or (topic_meta or {}).get("system", "")
    point_id = body.get("point_id") or (topic_meta or {}).get("point", "")
    series_id = body.get("series_id") or f"{site_id}#{building_id}#{system_id}#{point_id}"
    ts_ms = int(body.get("ts_ms") or 0)
    return {
        "device_id": series_id,
        "series_id": series_id,
        "ts_ms": ts_ms,
        "site_id": site_id,
        "building_id": building_id,
        "system_id": system_id,
        "point_id": point_id,
        "building_scope": building_scope(site_id, building_id),
        "scope_sort": scope_sort_key(system_id, point_id, ts_ms),
        "value": body.get("value"),
        "unit": body.get("unit", ""),
        "brick_class": body.get("brick_class", ""),
        "brick_tag": body.get("brick_tag", ""),
        "object_name": body.get("object_name", ""),
        "source": "bacnet",
        "seq": int(body.get("seq", 0)),
        "ts_iso": str(body.get("ts", "")),
        "bacnet_object": body.get("object"),
    }
