"""
AWS IoT Rule → Lambda: persist DS18B20 JSON telemetry to DynamoDB.

Expects MQTT JSON like aws_iot_publisher.build_payload() (degC, degF, seq, ts, source).
IoT Rule SQL: SELECT * FROM 'sdk/test/python'  (JSON keys arrive at event top level)
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any

from decimal import Decimal

import boto3

TABLE_NAME = os.environ.get("TABLE_NAME", "vibe12-telemetry")
DEVICE_ID = os.environ.get("DEVICE_ID", "bosspi-ds18b20")
TTL_DAYS = int(os.environ.get("TTL_DAYS", "7"))

_ddb = boto3.resource("dynamodb")
_table = _ddb.Table(TABLE_NAME)


def _parse_event(event: dict[str, Any]) -> dict[str, Any]:
    """Normalize IoT Rule payload (top-level JSON or wrapped string)."""
    if "degC" in event and "degF" in event:
        return event
    for key in ("payload", "data", "message"):
        raw = event.get(key)
        if raw is None:
            continue
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8", errors="replace")
        if isinstance(raw, str):
            return json.loads(raw)
        if isinstance(raw, dict):
            return raw
    raise ValueError(f"Unrecognized IoT event shape: {list(event.keys())}")


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


def lambda_handler(event, context):
    body = _parse_event(event if isinstance(event, dict) else {})

    deg_c = float(body["degC"])
    deg_f = float(body["degF"])
    seq = int(body.get("seq", 0))
    source = str(body.get("source", "ds18b20"))
    ts_iso = str(body.get("ts") or datetime.now(timezone.utc).isoformat())
    epoch_ms = _epoch_ms_from_ts(ts_iso)
    expires_at = int(time.time()) + TTL_DAYS * 86400

    item = {
        "device_id": DEVICE_ID,
        "ts_ms": epoch_ms,
        "ts_iso": ts_iso,
        "degC": Decimal(str(round(deg_c, 3))),
        "degF": Decimal(str(round(deg_f, 3))),
        "seq": seq,
        "source": source,
        "expires_at": expires_at,
    }

    _table.put_item(Item=item)

    return {
        "ok": True,
        "device_id": DEVICE_ID,
        "ts_ms": epoch_ms,
        "degC": deg_c,
        "degF": deg_f,
    }
