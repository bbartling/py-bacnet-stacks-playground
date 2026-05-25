"""Time-series read abstraction (DynamoDB v1; Timestream-ready)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from boto3.dynamodb.conditions import Key

from mqtt_routing import (
    BRICK_FDD_SUMMARY_TS,
    BRICK_GRAPH_TS,
    BRICK_TTL_TS,
    CANONICAL_MODEL_TS,
    POINT_REGISTRY_TS,
    building_scope,
    meta_device_id,
)


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, list):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    return obj


def _sample_to_reading(item: dict[str, Any]) -> dict[str, Any]:
    if "degC" in item and "degF" in item:
        return {
            "ts_ms": int(item["ts_ms"]),
            "ts": item.get("ts_iso", ""),
            "degC": float(item["degC"]),
            "degF": float(item["degF"]),
            "value": float(item.get("degF", item["degC"])),
            "source": item.get("source", "bacnet"),
        }
    val = item.get("value")
    if isinstance(val, Decimal):
        val = float(val)
    return {
        "ts_ms": int(item["ts_ms"]),
        "ts": item.get("ts_iso", ""),
        "value": val,
        "unit": item.get("unit", ""),
        "series_id": item.get("series_id") or item.get("device_id"),
        "source": item.get("source", "bacnet"),
    }


class DynamoTimeSeriesStore:
    def __init__(self, table, *, read_limit: int = 62000):
        self._table = table
        self._read_limit = read_limit

    def get_series(
        self,
        series_id: str,
        *,
        hours: int = 24,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        cutoff = int((time.time() - hours * 3600) * 1000)
        cap = limit or self._read_limit
        resp = self._table.query(
            KeyConditionExpression=Key("device_id").eq(series_id)
            & Key("ts_ms").gte(cutoff),
            ScanIndexForward=True,
            Limit=cap,
        )
        return [_sample_to_reading(x) for x in resp.get("Items", [])]

    def get_multi_series(
        self,
        series_ids: list[str],
        *,
        hours: int = 24,
    ) -> dict[str, list[dict[str, Any]]]:
        return {sid: self.get_series(sid, hours=hours) for sid in series_ids}

    def list_buildings(self) -> list[dict[str, str]]:
        """Scan meta# rows from point registry (best-effort)."""
        out: list[dict[str, str]] = []
        seen: set[str] = set()
        scan_args = {
            "FilterExpression": "begins_with(device_id, :p) AND ts_ms = :t",
            "ExpressionAttributeValues": {":p": "meta#", ":t": POINT_REGISTRY_TS},
            "Limit": 200,
        }
        while True:
            resp = self._table.scan(**scan_args)
            for item in resp.get("Items", []):
                site_id = item.get("site_id", "")
                building_id = item.get("building_id", "")
                scope = f"{site_id}#{building_id}"
                if scope in seen:
                    continue
                seen.add(scope)
                out.append(
                    {
                        "site_id": site_id,
                        "building_id": building_id,
                        "building_scope": building_scope(site_id, building_id),
                    }
                )
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_args["ExclusiveStartKey"] = last_key
        return out

    def ensure_building(self, site_id: str, building_id: str) -> None:
        """Create empty point-registry meta row so UI can register a site before first MQTT."""
        meta_id = meta_device_id(site_id, building_id)
        resp = self._table.get_item(
            Key={"device_id": meta_id, "ts_ms": POINT_REGISTRY_TS}
        )
        if resp.get("Item"):
            return
        import time

        self._table.put_item(
            Item={
                "device_id": meta_id,
                "ts_ms": POINT_REGISTRY_TS,
                "record_type": "point_registry",
                "site_id": site_id,
                "building_id": building_id,
                "points_json": "{}",
                "expires_at": int(time.time()) + 30 * 86400,
            }
        )

    def list_points(self, site_id: str, building_id: str) -> list[dict[str, Any]]:
        meta_id = meta_device_id(site_id, building_id)
        resp = self._table.get_item(
            Key={"device_id": meta_id, "ts_ms": POINT_REGISTRY_TS}
        )
        item = resp.get("Item") or {}
        raw = item.get("points_json") or "{}"
        if isinstance(raw, str):
            points_map = json.loads(raw) if raw else {}
        else:
            points_map = raw
        return [_json_safe(v) for v in points_map.values()]

    def query_by_building(
        self,
        site_id: str,
        building_id: str,
        *,
        hours: int = 24,
        brick_class: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        points = self.list_points(site_id, building_id)
        if brick_class:
            points = [p for p in points if p.get("brick_class") == brick_class]
        series_ids = [p["series_id"] for p in points if p.get("series_id")]
        return self.get_multi_series(series_ids, hours=hours)

    def get_brick_graph(self, site_id: str, building_id: str) -> dict[str, Any] | None:
        meta_id = meta_device_id(site_id, building_id)
        resp = self._table.get_item(
            Key={"device_id": meta_id, "ts_ms": BRICK_GRAPH_TS}
        )
        item = resp.get("Item")
        if not item:
            return None
        raw = item.get("graph_json") or item.get("graph")
        if isinstance(raw, str):
            return json.loads(raw)
        return raw

    def put_brick_graph(self, site_id: str, building_id: str, graph: dict[str, Any]) -> None:
        meta_id = meta_device_id(site_id, building_id)
        self._table.put_item(
            Item={
                "device_id": meta_id,
                "ts_ms": BRICK_GRAPH_TS,
                "record_type": "brick_graph",
                "site_id": site_id,
                "building_id": building_id,
                "graph_json": json.dumps(graph),
                "expires_at": int(time.time()) + 30 * 86400,
            }
        )

    def get_canonical_model(self, site_id: str, building_id: str) -> dict[str, Any] | None:
        meta_id = meta_device_id(site_id, building_id)
        resp = self._table.get_item(
            Key={"device_id": meta_id, "ts_ms": CANONICAL_MODEL_TS}
        )
        item = resp.get("Item")
        if not item:
            return None
        raw = item.get("model_json")
        if isinstance(raw, str):
            return json.loads(raw) if raw else None
        return raw

    def put_canonical_model(self, site_id: str, building_id: str, model: dict[str, Any]) -> None:
        meta_id = meta_device_id(site_id, building_id)
        now = int(time.time())
        self._table.put_item(
            Item={
                "device_id": meta_id,
                "ts_ms": CANONICAL_MODEL_TS,
                "record_type": "canonical_model",
                "site_id": site_id,
                "building_id": building_id,
                "model_json": json.dumps(model),
                "updated_at": now,
                "expires_at": now + 30 * 86400,
            }
        )

    def get_ttl(self, site_id: str, building_id: str) -> str | None:
        meta_id = meta_device_id(site_id, building_id)
        resp = self._table.get_item(Key={"device_id": meta_id, "ts_ms": BRICK_TTL_TS})
        item = resp.get("Item")
        if not item:
            return None
        return item.get("ttl_text") or item.get("ttl")

    def get_ttl_status(self, site_id: str, building_id: str) -> dict[str, Any]:
        meta_id = meta_device_id(site_id, building_id)
        resp = self._table.get_item(Key={"device_id": meta_id, "ts_ms": BRICK_TTL_TS})
        item = resp.get("Item") or {}
        return {
            "last_sync_iso": item.get("synced_at_iso", ""),
            "last_sync_ms": int(item.get("synced_at_ms") or 0),
            "last_sync_error": item.get("sync_error", ""),
        }

    def put_ttl(self, site_id: str, building_id: str, ttl_text: str, *, sync_error: str = "") -> None:
        meta_id = meta_device_id(site_id, building_id)
        now = int(time.time())

        self._table.put_item(
            Item={
                "device_id": meta_id,
                "ts_ms": BRICK_TTL_TS,
                "record_type": "brick_ttl",
                "site_id": site_id,
                "building_id": building_id,
                "ttl_text": ttl_text,
                "synced_at_ms": now,
                "synced_at_iso": datetime.now(timezone.utc).isoformat(),
                "sync_error": sync_error or "",
                "expires_at": now + 30 * 86400,
            }
        )

    def get_brick_fdd_summary(self, site_id: str, building_id: str) -> dict[str, Any] | None:
        meta_id = meta_device_id(site_id, building_id)
        resp = self._table.get_item(
            Key={"device_id": meta_id, "ts_ms": BRICK_FDD_SUMMARY_TS}
        )
        item = resp.get("Item")
        if not item:
            return None
        raw = item.get("summary_json")
        if isinstance(raw, str):
            return json.loads(raw) if raw else None
        return raw

    def put_brick_fdd_summary(self, site_id: str, building_id: str, summary: dict[str, Any]) -> None:
        meta_id = meta_device_id(site_id, building_id)
        now = int(time.time())
        self._table.put_item(
            Item={
                "device_id": meta_id,
                "ts_ms": BRICK_FDD_SUMMARY_TS,
                "record_type": "brick_fdd_summary",
                "site_id": site_id,
                "building_id": building_id,
                "summary_json": json.dumps(summary),
                "updated_at": now,
                "expires_at": now + 30 * 86400,
            }
        )

    def list_buildings_with_model(self) -> list[dict[str, str]]:
        """Buildings that have a canonical model row."""
        out: list[dict[str, str]] = []
        seen: set[str] = set()
        resp = self._table.scan(
            FilterExpression="begins_with(device_id, :p) AND ts_ms = :t",
            ExpressionAttributeValues={":p": "meta#", ":t": CANONICAL_MODEL_TS},
            Limit=200,
        )
        for item in resp.get("Items", []):
            scope = f"{item.get('site_id')}#{item.get('building_id')}"
            if scope in seen:
                continue
            seen.add(scope)
            out.append(
                {
                    "site_id": item.get("site_id", ""),
                    "building_id": item.get("building_id", ""),
                    "building_scope": building_scope(
                        item.get("site_id", ""), item.get("building_id", "")
                    ),
                }
            )
        return out

def align_series_windows(
    series_map: dict[str, list[dict[str, Any]]],
) -> tuple[list[int], dict[str, list[float | None]]]:
    """Align by ts_ms union; return sorted timestamps + value lists per series."""
    all_ts: set[int] = set()
    for samples in series_map.values():
        for s in samples:
            all_ts.add(int(s["ts_ms"]))
    ts_sorted = sorted(all_ts)
    aligned: dict[str, list[float | None]] = {}
    for sid, samples in series_map.items():
        by_ts = {int(s["ts_ms"]): s.get("value") for s in samples}
        aligned[sid] = [by_ts.get(t) for t in ts_sorted]
    return ts_sorted, aligned
