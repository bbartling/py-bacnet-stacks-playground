"""
AWS IoT Rule → Lambda: persist DS18B20 or BACnet telemetry to DynamoDB.

Topics:
  Legacy: sdk/test/python
  BACnet: vibe12/{site}/{building}/{system}/{point}/telemetry
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3

from mqtt_routing import (
    is_legacy_ds18b20,
    is_series_telemetry,
    parse_mqtt_topic,
    series_row_from_bacnet,
)

TABLE_NAME = os.environ.get("TABLE_NAME", "vibe12-telemetry")
DEVICE_ID = os.environ.get("DEVICE_ID", "bosspi-ds18b20")
TTL_DAYS = int(os.environ.get("TTL_DAYS", "7"))
BRICK_GRAPH_TS = -10
POINT_REGISTRY_TS = -11

_ddb = boto3.resource("dynamodb")
_table = _ddb.Table(TABLE_NAME)


def _parse_event(event: dict[str, Any]) -> dict[str, Any]:
    if isinstance(event, dict) and ("degC" in event or "series_id" in event or "value" in event):
        body = dict(event)
    else:
        body = {}
        for key in ("payload", "data", "message"):
            raw = event.get(key) if isinstance(event, dict) else None
            if raw is None:
                continue
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8", errors="replace")
            if isinstance(raw, str):
                body = json.loads(raw)
                break
            if isinstance(raw, dict):
                body = raw
                break
        if not body and isinstance(event, dict):
            body = {k: v for k, v in event.items() if k not in ("mqtt_topic", "topic")}
    if "mqtt_topic" not in body and isinstance(event, dict):
        body["mqtt_topic"] = event.get("mqtt_topic") or event.get("topic")
    return body


def _epoch_ms_from_ts(ts: str | None) -> int:
    if not ts:
        return int(time.time() * 1000)
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return int(time.time() * 1000)


def _dec(val) -> Decimal:
    return Decimal(str(val))


def _expires_at() -> int:
    return int(time.time()) + TTL_DAYS * 86400


def _put_legacy(body: dict[str, Any]) -> dict[str, Any]:
    deg_c = float(body["degC"])
    deg_f = float(body["degF"])
    seq = int(body.get("seq", 0))
    source = str(body.get("source", "ds18b20"))
    ts_iso = str(body.get("ts") or datetime.now(timezone.utc).isoformat())
    epoch_ms = _epoch_ms_from_ts(ts_iso)

    item = {
        "device_id": DEVICE_ID,
        "ts_ms": epoch_ms,
        "ts_iso": ts_iso,
        "degC": _dec(round(deg_c, 3)),
        "degF": _dec(round(deg_f, 3)),
        "seq": seq,
        "source": source,
        "expires_at": _expires_at(),
    }
    _table.put_item(Item=item)
    return {"ok": True, "mode": "legacy", "device_id": DEVICE_ID, "ts_ms": epoch_ms}


def _upsert_point_registry(row: dict[str, Any]) -> None:
    meta_id = f"meta#{row['site_id']}#{row['building_id']}"
    reg_key = row["series_id"]
    try:
        resp = _table.get_item(Key={"device_id": meta_id, "ts_ms": POINT_REGISTRY_TS})
        reg = resp.get("Item") or {}
        points = reg.get("points_json") or "{}"
        if isinstance(points, str):
            points_map = json.loads(points) if points else {}
        else:
            points_map = points
    except Exception:
        points_map = {}

    points_map[reg_key] = {
        "series_id": row["series_id"],
        "site_id": row["site_id"],
        "building_id": row["building_id"],
        "system_id": row["system_id"],
        "point_id": row["point_id"],
        "unit": row.get("unit", ""),
        "brick_class": row.get("brick_class", ""),
        "brick_tag": row.get("brick_tag", ""),
        "object_name": row.get("object_name", ""),
    }
    _table.put_item(
        Item={
            "device_id": meta_id,
            "ts_ms": POINT_REGISTRY_TS,
            "record_type": "point_registry",
            "site_id": row["site_id"],
            "building_id": row["building_id"],
            "points_json": json.dumps(points_map),
            "expires_at": int(time.time()) + 30 * 86400,
        }
    )


def _put_bacnet(body: dict[str, Any], topic: str | None) -> dict[str, Any]:
    topic_meta = parse_mqtt_topic(topic or body.get("mqtt_topic"))
    row = series_row_from_bacnet(body, topic_meta)
    if not row["ts_ms"]:
        row["ts_ms"] = _epoch_ms_from_ts(body.get("ts"))

    val = row["value"]
    item = {
        "device_id": row["series_id"],
        "series_id": row["series_id"],
        "ts_ms": row["ts_ms"],
        "ts_iso": row["ts_iso"] or datetime.now(timezone.utc).isoformat(),
        "site_id": row["site_id"],
        "building_id": row["building_id"],
        "system_id": row["system_id"],
        "point_id": row["point_id"],
        "building_scope": row["building_scope"],
        "scope_sort": row["scope_sort"],
        "value": _dec(val) if val is not None and isinstance(val, (int, float)) else val,
        "unit": row["unit"],
        "brick_class": row["brick_class"],
        "brick_tag": row["brick_tag"],
        "object_name": row["object_name"],
        "source": row["source"],
        "seq": row["seq"],
        "expires_at": _expires_at(),
    }
    if row.get("bacnet_object"):
        item["bacnet_object"] = json.dumps(row["bacnet_object"])
    _table.put_item(Item=item)
    try:
        _upsert_point_registry(row)
    except Exception:
        pass
    return {"ok": True, "mode": "bacnet", "series_id": row["series_id"], "ts_ms": row["ts_ms"]}


def lambda_handler(event, context):
    body = _parse_event(event if isinstance(event, dict) else {})
    topic = body.get("mqtt_topic")
    if not topic and isinstance(event, dict):
        topic = event.get("mqtt_topic")

    if is_series_telemetry(body):
        return _put_bacnet(body, topic)

    if is_legacy_ds18b20(body):
        return _put_legacy(body)

    if topic and parse_mqtt_topic(topic):
        return _put_bacnet(body, topic)

    raise ValueError(f"Unrecognized telemetry payload: keys={list(body.keys())}")
