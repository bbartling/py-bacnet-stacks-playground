"""Telemetry flow + AI commissioning APIs."""

from __future__ import annotations

import time
from typing import Any

from boto3.dynamodb.conditions import Key

from brick_timeseries import brick_timeseries_ref, parse_stored_ref
from mqtt_routing import building_scope, meta_device_id

# Freshness thresholds (minutes since last sample)
FRESH_GREEN_MAX_MIN = 20
FRESH_YELLOW_MAX_MIN = 40
FRESH_ORANGE_MAX_MIN = 60


def ingest_freshness(last_ms: int, *, now_ms: int | None = None) -> dict[str, Any]:
    """Map last ingest timestamp to UI status: green / yellow / orange / red / offline."""
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    if not last_ms or last_ms <= 0:
        return {
            "status": "offline",
            "age_minutes": None,
            "last_ts_ms": 0,
            "label": "No data",
        }
    age_min = max(0, (now - int(last_ms)) // 60000)
    if age_min < FRESH_GREEN_MAX_MIN:
        status, label = "green", "Live"
    elif age_min < FRESH_YELLOW_MAX_MIN:
        status, label = "yellow", f"Stale {age_min}m"
    elif age_min < FRESH_ORANGE_MAX_MIN:
        status, label = "orange", f"Delayed {age_min}m"
    else:
        status, label = "red", f"Offline {age_min}m"
    return {
        "status": status,
        "age_minutes": age_min,
        "last_ts_ms": int(last_ms),
        "label": label,
    }


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
        fresh = ingest_freshness(last_ms, now_ms=now_ms)
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
                "freshness": fresh,
                "ingest_status": fresh["status"],
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


def telemetry_series_catalog(store, *, hours: int = 24) -> dict[str, Any]:
    """All registered series across buildings — for raw explore plotting without BRICK model."""
    now_ms = int(time.time() * 1000)
    buildings = store.list_buildings()
    catalog: list[dict[str, Any]] = []
    for b in buildings:
        site_id = b.get("site_id", "")
        building_id = b.get("building_id", "")
        for p in store.list_points(site_id, building_id):
            sid = p.get("series_id") or ""
            if not sid:
                continue
            last = _latest_sample(store._table, sid)
            last_ms = int(last["ts_ms"]) if last else 0
            fresh = ingest_freshness(last_ms, now_ms=now_ms)
            ref = parse_stored_ref((last or {}).get("brick_timeseries_ref")) or p.get(
                "brick_timeseries_ref"
            )
            if isinstance(ref, str):
                ref = parse_stored_ref(ref)
            has_brick_ref = bool(ref and ref.get("entity_id"))
            catalog.append(
                {
                    "series_id": sid,
                    "site_id": site_id,
                    "building_id": building_id,
                    "system_id": p.get("system_id"),
                    "point_id": p.get("point_id"),
                    "source": p.get("source") or (last or {}).get("source"),
                    "brick_class": p.get("brick_class"),
                    "unit": p.get("unit") or (last or {}).get("unit"),
                    "last_value": float(last["value"])
                    if last and last.get("value") is not None
                    else None,
                    "freshness": fresh,
                    "has_brick_timeseries_ref": has_brick_ref,
                    "entity_id": (ref or {}).get("entity_id") if ref else p.get("entity_id"),
                }
            )
    catalog.sort(key=lambda x: (x.get("site_id", ""), x.get("series_id", "")))
    return {
        "hours_default": hours,
        "checked_at_ms": now_ms,
        "buildings_count": len(buildings),
        "series_count": len(catalog),
        "series": catalog,
    }


def edge_devices_status(store) -> dict[str, Any]:
    """Edge IoT / BACnet ingest health for all buildings and series."""
    now_ms = int(time.time() * 1000)
    buildings = store.list_buildings()
    building_rows: list[dict[str, Any]] = []
    all_series: list[dict[str, Any]] = []
    for b in buildings:
        site_id = b.get("site_id", "")
        building_id = b.get("building_id", "")
        flow = telemetry_flow_status(store, site_id, building_id, window_minutes=60)
        statuses = [s.get("ingest_status") or "offline" for s in flow["series"]]
        if not statuses:
            b_status = "offline"
        elif all(s == "green" for s in statuses):
            b_status = "green"
        elif any(s == "green" for s in statuses):
            b_status = "yellow"
        elif any(s in ("yellow", "orange") for s in statuses):
            b_status = "orange"
        else:
            b_status = "red"
        building_rows.append(
            {
                "site_id": site_id,
                "building_id": building_id,
                "building_scope": b.get("building_scope")
                or building_scope(site_id, building_id),
                "ingest_status": b_status,
                "series_total": flow["series_total"],
                "series_flowing": flow["series_flowing"],
                "cloud_ingest_ok": flow["cloud_ingest_ok"],
                "last_activity_ms": max(
                    (s.get("last_ts_ms") or 0 for s in flow["series"]), default=0
                ),
            }
        )
        all_series.extend(flow["series"])
    return {
        "checked_at_ms": now_ms,
        "freshness_thresholds_minutes": {
            "green": FRESH_GREEN_MAX_MIN,
            "yellow": FRESH_YELLOW_MAX_MIN,
            "orange": FRESH_ORANGE_MAX_MIN,
            "red_after": FRESH_ORANGE_MAX_MIN,
        },
        "buildings": building_rows,
        "series": all_series,
        "buildings_count": len(building_rows),
        "series_count": len(all_series),
    }


def deployment_readiness(store, *, deploy_revision: str = "") -> dict[str, Any]:
    """Operator checklist: what is configured vs missing before go-live."""
    buildings = store.list_buildings()
    checks: list[dict[str, Any]] = []
    series_with_ref = 0
    series_total = 0
    any_flowing = False

    if not buildings:
        checks.append(
            {
                "id": "sites",
                "label": "Site / building registered",
                "ok": False,
                "hint": "Create a site under Sites tab or publish edge MQTT with site_id/building_id.",
            }
        )
    else:
        checks.append(
            {
                "id": "sites",
                "label": "Site / building registered",
                "ok": True,
                "detail": f"{len(buildings)} building(s) in DynamoDB",
            }
        )

    for b in buildings:
        site_id = b["site_id"]
        building_id = b["building_id"]
        points = store.list_points(site_id, building_id)
        series_total += len(points)
        model = store.get_canonical_model(site_id, building_id)
        graph = store.get_brick_graph(site_id, building_id)
        flow = telemetry_flow_status(store, site_id, building_id, window_minutes=20)
        if flow["series_flowing"] > 0:
            any_flowing = True
        for p in points:
            ref = p.get("brick_timeseries_ref")
            if isinstance(ref, dict) and ref.get("entity_id"):
                series_with_ref += 1
            elif isinstance(ref, str) and "entity_id" in ref:
                series_with_ref += 1
        checks.append(
            {
                "id": f"model_{site_id}_{building_id}",
                "label": f"Canonical model · {site_id}/{building_id}",
                "ok": model is not None and bool(model.get("points")),
                "detail": f"{len(model.get('points', [])) if model else 0} model points",
            }
        )
        checks.append(
            {
                "id": f"graph_{site_id}_{building_id}",
                "label": f"BRICK graph · {site_id}/{building_id}",
                "ok": graph is not None,
                "hint": "Data Model → Sync TTL or Import JSON",
            }
        )
        checks.append(
            {
                "id": f"ingest_{site_id}_{building_id}",
                "label": f"Cloud ingest (20m) · {site_id}/{building_id}",
                "ok": flow["cloud_ingest_ok"],
                "detail": f"{flow['series_flowing']}/{flow['series_total']} flowing",
            }
        )

    checks.insert(
        1,
        {
            "id": "telemetry",
            "label": "Telemetry series in registry",
            "ok": series_total > 0,
            "detail": f"{series_total} series",
        },
    )
    checks.insert(
        2,
        {
            "id": "brick_refs",
            "label": "BRICK timeseries refs on registry",
            "ok": series_total > 0 and series_with_ref >= series_total,
            "detail": f"{series_with_ref}/{series_total} with entity_id",
            "hint": "Ingest Lambda writes brick_timeseries_ref on each MQTT sample; registry updates on ingest.",
        },
    )
    checks.insert(
        3,
        {
            "id": "cloud_ingest",
            "label": "Any series ingested recently",
            "ok": any_flowing,
            "hint": "Check edge gateway MQTT, IoT policy, and ingest rule.",
        },
    )

    if deploy_revision:
        checks.append(
            {
                "id": "deploy_revision",
                "label": "Cloud deploy revision",
                "ok": True,
                "detail": deploy_revision,
            }
        )

    ok_count = sum(1 for c in checks if c.get("ok"))
    return {
        "ready": ok_count == len(checks) and series_total > 0 and any_flowing,
        "checks_ok": ok_count,
        "checks_total": len(checks),
        "checks": checks,
        "series_total": series_total,
        "series_with_brick_ref": series_with_ref,
    }
