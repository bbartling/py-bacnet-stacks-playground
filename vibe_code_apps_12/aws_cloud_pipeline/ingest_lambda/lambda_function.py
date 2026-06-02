"""
AWS IoT Rule → Lambda: persist BACnet / edge telemetry to DynamoDB.

Topic: {IOT_TOPIC_PREFIX}/{site}/{building}/{system}/{point}/telemetry
       {IOT_TOPIC_PREFIX}/{site}/{building}/batch/telemetry  (batched poll cycle)
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3

from brick_timeseries import brick_timeseries_ref, registry_entry_from_row
from mqtt_routing import (
    is_batch_telemetry,
    is_series_telemetry,
    parse_batch_topic,
    parse_mqtt_topic,
    series_row_from_bacnet,
)

TABLE_NAME = os.environ.get("TABLE_NAME", "vibe12-telemetry")
TTL_DAYS = int(os.environ.get("TTL_DAYS", "7"))
BRICK_GRAPH_TS = -10
POINT_REGISTRY_TS = -11

_ddb = boto3.resource("dynamodb")
_table = _ddb.Table(TABLE_NAME)


def _parse_event(event: dict[str, Any]) -> dict[str, Any]:
    if isinstance(event, dict) and ("series_id" in event or "value" in event):
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


def _infer_equipment_type(system_id: str) -> str:
    """Best-effort BRICK equipment class from BACnet system_id."""
    s = (system_id or "").lower()
    if "vav" in s:
        return "Variable_Air_Volume_Box"
    if "ahu" in s:
        return "Air_Handling_Unit"
    if "chiller" in s:
        return "Chiller"
    if "boiler" in s:
        return "Boiler"
    return "HVAC_Equipment"


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

    system_id = row.get("system_id") or ""
    entry = registry_entry_from_row(
        {
            **row,
            "equipment_type": _infer_equipment_type(system_id),
        }
    )
    points_map[reg_key] = entry
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


def _put_telemetry(body: dict[str, Any], topic: str | None) -> dict[str, Any]:
    topic_meta = parse_mqtt_topic(topic or body.get("mqtt_topic"))
    row = series_row_from_bacnet(body, topic_meta)
    if not row["ts_ms"]:
        row["ts_ms"] = _epoch_ms_from_ts(body.get("ts"))
    if not row["series_id"] or "#" not in row["series_id"]:
        raise ValueError(
            "telemetry requires site/building/system/point "
            f"(topic={topic!r} keys={list(body.keys())})"
        )

    val = row["value"]
    ts_ref = brick_timeseries_ref(
        site_id=row["site_id"],
        building_id=row["building_id"],
        system_id=row["system_id"],
        point_id=row["point_id"],
        series_id=row["series_id"],
        brick_class=row.get("brick_class", ""),
        brick_tag=row.get("brick_tag", ""),
    )
    ts_ref["hasUnit"] = row.get("unit", "")
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
        "brick_timeseries_ref": json.dumps(ts_ref),
        "external_ref": row["series_id"],
        "entity_id": ts_ref["entity_id"],
        "expires_at": _expires_at(),
    }
    if row.get("bacnet_object"):
        item["bacnet_object"] = json.dumps(row["bacnet_object"])
    _table.put_item(Item=item)
    try:
        _upsert_point_registry(row)
    except Exception:
        pass
    return {"ok": True, "mode": "telemetry", "series_id": row["series_id"], "ts_ms": row["ts_ms"]}


def _put_batch_telemetry(body: dict[str, Any], topic: str | None) -> dict[str, Any]:
    samples = body.get("samples") or []
    if not isinstance(samples, list):
        raise ValueError("batch telemetry requires samples array")
    batch_meta = parse_batch_topic(topic or body.get("mqtt_topic"))
    site_id = body.get("site_id") or (batch_meta or {}).get("site", "")
    building_id = body.get("building_id") or (batch_meta or {}).get("building", "")
    ingested: list[dict[str, Any]] = []
    errors: list[str] = []
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        sample_body = dict(sample)
        if site_id and not sample_body.get("site_id"):
            sample_body["site_id"] = site_id
        if building_id and not sample_body.get("building_id"):
            sample_body["building_id"] = building_id
        try:
            result = _put_telemetry(sample_body, topic)
            ingested.append(result)
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
    if not ingested and errors:
        raise ValueError(f"batch ingest failed: {errors[0]}")
    return {
        "ok": True,
        "mode": "batch",
        "ingested": len(ingested),
        "errors": errors,
        "site_id": site_id,
        "building_id": building_id,
    }


def lambda_handler(event, context):
    body = _parse_event(event if isinstance(event, dict) else {})
    topic = body.get("mqtt_topic")
    if not topic and isinstance(event, dict):
        topic = event.get("mqtt_topic")

    if is_batch_telemetry(body):
        return _put_batch_telemetry(body, topic)

    if is_series_telemetry(body):
        return _put_telemetry(body, topic)

    if topic and parse_mqtt_topic(topic):
        return _put_telemetry(body, topic)

    if topic and parse_batch_topic(topic):
        return _put_batch_telemetry(body, topic)

    raise ValueError(f"Unrecognized telemetry payload: keys={list(body.keys())} topic={topic!r}")
