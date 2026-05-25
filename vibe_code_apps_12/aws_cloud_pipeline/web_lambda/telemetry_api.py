"""Telemetry flow + AI commissioning APIs."""

from __future__ import annotations

import time
from typing import Any

from boto3.dynamodb.conditions import Key

from brick_timeseries import brick_timeseries_ref, parse_stored_ref
from mqtt_routing import building_scope, meta_device_id


def _latest_sample(table, series_id: str) -> dict[str, Any] | None:
    resp = table.query(
        KeyConditionExpression=Key("device_id").eq(series_id),
        ScanIndexForward=False,
        Limit=1,
    )
    items = resp.get("Items") or []
    return items[0] if items else None


def telemetry_flow_status(
    store,
    site_id: str,
    building_id: str,
    *,
    window_minutes: int = 15,
) -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    cutoff_ms = now_ms - window_minutes * 60 * 1000
    points = store.list_points(site_id, building_id)
    series_status: list[dict[str, Any]] = []
    flowing = 0
    for p in points:
        sid = p.get("series_id") or ""
        if not sid:
            continue
        last = _latest_sample(store._table, sid)
        last_ms = int(last["ts_ms"]) if last else 0
        is_flowing = last_ms >= cutoff_ms
        if is_flowing:
            flowing += 1
        ref = parse_stored_ref((last or {}).get("brick_timeseries_ref")) or p.get(
            "brick_timeseries_ref"
        )
        if not ref and isinstance(p.get("brick_timeseries_ref"), dict):
            ref = p["brick_timeseries_ref"]
        if not ref:
            ref = brick_timeseries_ref(
                site_id=site_id,
                building_id=building_id,
                system_id=p.get("system_id", ""),
                point_id=p.get("point_id", ""),
                series_id=sid,
                brick_class=p.get("brick_class", ""),
                brick_tag=p.get("brick_tag", ""),
                unit=p.get("unit", ""),
            )
        series_status.append(
            {
                "series_id": sid,
                "point_id": p.get("point_id"),
                "system_id": p.get("system_id"),
                "source": p.get("source") or (last or {}).get("source"),
                "brick_class": p.get("brick_class"),
                "brick_tag": p.get("brick_tag"),
                "object_name": p.get("object_name"),
                "flowing": is_flowing,
                "last_ts_ms": last_ms,
                "last_value": float(last["value"]) if last and last.get("value") is not None else None,
                "last_unit": (last or {}).get("unit") or p.get("unit"),
                "brick_timeseries_ref": ref,
                "entity_id": ref.get("entity_id") if ref else p.get("entity_id"),
                "external_ref": sid,
            }
        )
    return {
        "site_id": site_id,
        "building_id": building_id,
        "building_scope": building_scope(site_id, building_id),
        "window_minutes": window_minutes,
        "checked_at_ms": now_ms,
        "points_registered": len(points),
        "series_flowing": flowing,
        "series_total": len(series_status),
        "cloud_ingest_ok": flowing > 0,
        "series": series_status,
        "mqtt_topic_pattern": "vibe12/{site_id}/{building_id}/{system_id}/{point_id}/telemetry",
    }


def brick_timeseries_refs(
    store,
    site_id: str,
    building_id: str,
    *,
    series_id: str | None = None,
) -> dict[str, Any]:
    points = store.list_points(site_id, building_id)
    if series_id:
        points = [p for p in points if p.get("series_id") == series_id]
    refs = []
    for p in points:
        raw = p.get("brick_timeseries_ref")
        ref = parse_stored_ref(raw) if raw else None
        if not ref:
            ref = brick_timeseries_ref(
                site_id=site_id,
                building_id=building_id,
                system_id=p.get("system_id", ""),
                point_id=p.get("point_id", ""),
                series_id=p.get("series_id", ""),
                brick_class=p.get("brick_class", ""),
                brick_tag=p.get("brick_tag", ""),
                unit=p.get("unit", ""),
            )
        refs.append(
            {
                "series_id": p.get("series_id"),
                "brick_timeseries_ref": ref,
                "registry": p,
            }
        )
    return {
        "site_id": site_id,
        "building_id": building_id,
        "count": len(refs),
        "refs": refs,
    }


def commissioning_status(
    store,
    site_id: str,
    building_id: str,
    *,
    window_minutes: int = 15,
) -> dict[str, Any]:
    """AI/OpenClaw-friendly rollup: edge expectations vs cloud reality."""
    flow = telemetry_flow_status(
        store, site_id, building_id, window_minutes=window_minutes
    )
    by_source: dict[str, list[str]] = {}
    for s in flow["series"]:
        src = s.get("source") or "unknown"
        by_source.setdefault(src, []).append(s["series_id"])
    zat = [
        s
        for s in flow["series"]
        if s.get("brick_class") == "Zone_Air_Temperature_Sensor"
    ]
    return {
        **flow,
        "ai_hints": {
            "human_ssh": "Operator must SSH to edge for BACnet discover / points.csv validation.",
            "edge_publish": "vibe12-bacnet-read.service publishes BACnet + optional GPIO on one MQTT client.",
            "cloud_ingest": "IoT rule vibe12_telemetry_ingest → IngestFunction → DynamoDB.",
            "brick_next": "Use brick_timeseries_ref.external_ref as DynamoDB key for FDD + SparkQL.",
        },
        "by_source": by_source,
        "zone_air_temperature_sensors": zat,
        "recommended_actions": _recommended_actions(flow),
    }


def _recommended_actions(flow: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    if flow["points_registered"] == 0:
        actions.append(
            "No point registry in DynamoDB — verify IoT policy allows vibe12/# publish and ingest Lambda invocations."
        )
    if flow["series_total"] > 0 and flow["series_flowing"] == 0:
        actions.append(
            "Registry exists but no recent samples — check Pi journalctl vibe12-bacnet-read and IoT rule SQL."
        )
    if flow["series_flowing"] > 0 and not any(
        s.get("brick_class") == "Zone_Air_Temperature_Sensor" and s.get("flowing")
        for s in flow["series"]
    ):
        actions.append("No flowing Zone_Air_Temperature_Sensor — confirm MSTP ZN-T and/or GPIO DS18B20 enabled.")
    if not actions:
        actions.append("Telemetry flowing — proceed to BRICK graph validation and FDD rule authoring.")
    return actions
