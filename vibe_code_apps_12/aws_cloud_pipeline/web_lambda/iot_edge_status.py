"""AWS IoT Core thing / client connectivity (optional; complements telemetry freshness)."""

from __future__ import annotations

import json
import os
import time
from typing import Any

_THINGS_CACHE: tuple[float, list[dict[str, Any]]] | None = None
_CACHE_TTL_SEC = 45


def _parse_things_config() -> list[dict[str, Any]]:
    raw = os.environ.get("IOT_EDGE_THINGS", "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        site_id = str(item.get("site_id") or "").strip()
        building_id = str(item.get("building_id") or "").strip()
        if not site_id or not building_id:
            continue
        out.append(
            {
                "site_id": site_id,
                "building_id": building_id,
                "thing_name": str(item.get("thing_name") or "").strip(),
                "client_id": str(item.get("client_id") or "").strip(),
                "label": str(item.get("label") or item.get("thing_name") or item.get("client_id") or "edge"),
            }
        )
    return out


def _iot_client():
    import boto3

    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-2"
    return boto3.client("iot", region_name=region)


def _status_from_connectivity_api(thing_name: str) -> dict[str, Any] | None:
    if not thing_name:
        return None
    try:
        resp = _iot_client().get_thing_connectivity_data(thingName=thing_name)
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "") if hasattr(exc, "response") else ""
        return {
            "thing_name": thing_name,
            "connected": None,
            "source": "iot_get_thing_connectivity_data",
            "error": str(exc),
            "error_code": code or type(exc).__name__,
        }
    connected = resp.get("connected")
    at = resp.get("connectedAt") or resp.get("timestamp")
    last_ms = 0
    if at is not None:
        try:
            if hasattr(at, "timestamp"):
                last_ms = int(at.timestamp() * 1000)
            else:
                last_ms = int(at)
        except (TypeError, ValueError):
            last_ms = 0
    return {
        "thing_name": thing_name,
        "connected": bool(connected) if connected is not None else None,
        "last_connected_ms": last_ms,
        "disconnect_reason": resp.get("disconnectReason") or "",
        "source": "iot_get_thing_connectivity_data",
    }


def _status_from_search_index(*, thing_name: str = "", client_id: str = "") -> dict[str, Any] | None:
    parts: list[str] = []
    if thing_name:
        parts.append(f"thingName:{thing_name}")
    if client_id:
        parts.append(f"clientId:{client_id}")
    if not parts:
        return None
    query = " AND ".join(parts)
    try:
        resp = _iot_client().search_index(queryString=query, maxResults=1)
    except Exception as exc:
        return {
            "connected": None,
            "source": "iot_search_index",
            "error": str(exc),
            "query": query,
        }
    things = resp.get("things") or []
    if not things:
        return {
            "connected": False,
            "source": "iot_search_index",
            "query": query,
            "note": "no index match — thing may be offline or fleet indexing disabled",
        }
    row = things[0]
    conn = row.get("connectivity") or {}
    connected = conn.get("connected")
    disc = conn.get("disconnectReason") or conn.get("disconnectReasonCode") or ""
    return {
        "thing_name": row.get("thingName") or thing_name,
        "client_id": row.get("clientId") or client_id,
        "connected": bool(connected) if connected is not None else None,
        "disconnect_reason": disc,
        "source": "iot_search_index",
        "query": query,
    }


def lookup_iot_edge_things(*, use_cache: bool = True) -> dict[str, Any]:
    """
    Poll configured IoT things/clients. Requires IOT_EDGE_THINGS JSON env on Web Lambda.

    Example env value:
    [{"site_id":"demo","building_id":"bens-office","thing_name":"bosspi","client_id":"basicPubSub","label":"Boss Pi"}]
    """
    global _THINGS_CACHE
    now = time.time()
    if use_cache and _THINGS_CACHE and (now - _THINGS_CACHE[0]) < _CACHE_TTL_SEC:
        return {"things": _THINGS_CACHE[1], "cached": True}

    config = _parse_things_config()
    if not config:
        return {
            "configured": False,
            "things": [],
            "hint": (
                "Set IOT_EDGE_THINGS on Web Lambda to poll IoT Core thing connectivity "
                "(telemetry freshness on Edge tab works without this)."
            ),
        }

    results: list[dict[str, Any]] = []
    for entry in config:
        row: dict[str, Any] = {
            "site_id": entry["site_id"],
            "building_id": entry["building_id"],
            "label": entry["label"],
            "thing_name": entry.get("thing_name") or "",
            "client_id": entry.get("client_id") or "",
            "mqtt_connected": None,
            "mqtt_status": "unknown",
            "iot_api_source": "",
        }
        st = None
        if entry.get("thing_name"):
            st = _status_from_connectivity_api(entry["thing_name"])
        if st is None or st.get("connected") is None:
            idx = _status_from_search_index(
                thing_name=entry.get("thing_name") or "",
                client_id=entry.get("client_id") or "",
            )
            if idx:
                st = {**(st or {}), **idx}
        if st:
            row["iot_api_source"] = st.get("source", "")
            if st.get("error"):
                row["iot_error"] = st.get("error")
                row["mqtt_status"] = "api_error"
            elif st.get("connected") is True:
                row["mqtt_connected"] = True
                row["mqtt_status"] = "connected"
            elif st.get("connected") is False:
                row["mqtt_connected"] = False
                row["mqtt_status"] = "disconnected"
                row["disconnect_reason"] = st.get("disconnect_reason") or ""
            else:
                row["mqtt_status"] = "unknown"
            if st.get("last_connected_ms"):
                row["last_connected_ms"] = st["last_connected_ms"]
        else:
            row["mqtt_status"] = "not_configured"
            row["note"] = "Add thing_name and enable IoT fleet connectivity indexing"
        results.append(row)

    _THINGS_CACHE = (now, results)
    return {"configured": True, "things": results, "cached": False}
