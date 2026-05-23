"""MQTT topic + JSON payload for BACnet telemetry."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from edge_bacnet.config import PointConfig

TOPIC_PREFIX = "vibe12"


def mqtt_topic_for_point(point: PointConfig) -> str:
    return (
        f"{TOPIC_PREFIX}/{point.site_id}/{point.building_id}/"
        f"{point.system_id}/{point.point_id}/telemetry"
    )


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
