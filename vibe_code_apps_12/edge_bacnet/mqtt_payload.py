"""MQTT topic + JSON payload for BACnet telemetry."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from edge_bacnet.config import PointConfig

TOPIC_PREFIX = "vibe12"


def mqtt_topic_for_ids(
    site_id: str,
    building_id: str,
    system_id: str,
    point_id: str,
) -> str:
    return (
        f"{TOPIC_PREFIX}/{site_id}/{building_id}/"
        f"{system_id}/{point_id}/telemetry"
    )


def mqtt_topic_for_point(point: PointConfig) -> str:
    return mqtt_topic_for_ids(
        point.site_id,
        point.building_id,
        point.system_id,
        point.point_id,
    )


def series_id_for(
    site_id: str,
    building_id: str,
    system_id: str,
    point_id: str,
) -> str:
    return f"{site_id}#{building_id}#{system_id}#{point_id}"


def build_edge_payload(
    *,
    site_id: str,
    building_id: str,
    system_id: str,
    point_id: str,
    value: Any,
    unit: str,
    seq: int = 0,
    ts_ms: int | None = None,
    brick_class: str = "",
    brick_tag: str = "",
    object_name: str = "",
) -> str:
    now = datetime.now(timezone.utc)
    if ts_ms is None:
        ts_ms = int(now.timestamp() * 1000)
    sid = series_id_for(site_id, building_id, system_id, point_id)
    body = {
        "source": "edge",
        "site_id": site_id,
        "building_id": building_id,
        "system_id": system_id,
        "point_id": point_id,
        "series_id": sid,
        "value": value,
        "unit": unit,
        "brick_class": brick_class,
        "brick_tag": brick_tag,
        "object_name": object_name,
        "seq": seq,
        "ts_ms": ts_ms,
        "ts": now.isoformat(),
    }
    return json.dumps(body)


def build_bacnet_payload(
    point: PointConfig,
    value: Any,
    *,
    seq: int = 0,
    ts_ms: int | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    if ts_ms is None:
        ts_ms = int(now.timestamp() * 1000)
    body = {
        "source": "bacnet",
        "site_id": point.site_id,
        "building_id": point.building_id,
        "system_id": point.system_id,
        "point_id": point.point_id,
        "series_id": point.series_id,
        "object": {
            "device": point.device_instance,
            "type": point.object_type,
            "instance": point.object_instance,
        },
        "value": value,
        "unit": point.units or "",
        "brick_class": point.brick_class or "",
        "brick_tag": point.brick_tag or "",
        "object_name": point.object_name or "",
        "seq": seq,
        "ts_ms": ts_ms,
        "ts": now.isoformat(),
    }
    return json.dumps(body)
