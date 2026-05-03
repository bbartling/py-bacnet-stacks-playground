"""Helpers for diy-bacnet schedule read + pushing occupancy to linked BACnet binary points."""
from __future__ import annotations

from typing import Any

from app import rpc_client, trend_store


def extract_schedule_present_value(payload: dict[str, Any]) -> Any | None:
    """Best-effort present / effective value from ``server_read_schedule`` JSON-RPC result."""
    r = payload.get("result")
    if r is None:
        r = payload
    if isinstance(r, (bool, int, float)):
        return r
    if not isinstance(r, dict):
        return None
    for key in ("present_value", "presentValue", "value", "occupied", "effective_value", "effectiveValue"):
        if key in r and r[key] is not None:
            return r[key]
    for sub in ("schedule", "data", "request"):
        inner = r.get(sub)
        if isinstance(inner, dict):
            nested = extract_schedule_present_value({"result": inner})
            if nested is not None:
                return nested
    return None


def occupancy_bool_from_schedule_value(v: Any) -> bool:
    """Map schedule present-value (float 0/1, bool, etc.) to a BACnet binary write."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v) and float(v) != 0.0
    if isinstance(v, str):
        s = v.strip().lower()
        return s in ("1", "true", "on", "yes", "active", "occupied")
    return False


def _active_profile(schedules_doc: dict[str, Any]) -> dict[str, Any] | None:
    schedules = schedules_doc.get("schedules") or []
    if not isinstance(schedules, list) or not schedules:
        return None
    active_id = schedules_doc.get("activeScheduleId")
    for s in schedules:
        if isinstance(s, dict) and s.get("id") == active_id:
            return s
    first = schedules[0]
    return first if isinstance(first, dict) else None


def read_schedule_status(*, object_name: str) -> dict[str, Any]:
    """Call diy-bacnet ``server_read_schedule`` and normalize for the UI."""
    err = ""
    raw: dict[str, Any] = {}
    pv: Any = None
    try:
        raw = rpc_client.server_read_schedule(object_name)
        pv = extract_schedule_present_value(raw)
    except Exception as exc:  # noqa: BLE001
        err = str(exc)
    return {
        "scheduleObjectName": object_name,
        "schedulePresentValue": pv,
        "scheduleOccupancyBool": occupancy_bool_from_schedule_value(pv),
        "scheduleReadError": err or None,
    }


def sync_linked_binary_outputs(schedules_doc: dict[str, Any], *, object_name: str) -> dict[str, Any]:
    """
    Read effective schedule value from diy-bacnet, then write priority-8 present-value
    to each linked **binary** commandable point on the **active** profile (``pointId`` set).
    """
    status = read_schedule_status(object_name=object_name)
    if status.get("scheduleReadError"):
        return {
            **status,
            "written": [],
            "errors": [{"detail": status["scheduleReadError"]}],
            "ok": False,
        }
    occ = bool(status.get("scheduleOccupancyBool"))
    prof = _active_profile(schedules_doc)
    if not prof:
        return {**status, "written": [], "errors": [{"detail": "no schedules"}], "ok": False}
    links = prof.get("bacnetPoints") or []
    if not isinstance(links, list):
        links = []
    rows = trend_store.read_points_merged_with_polling()
    by_id = {str(x.get("pointId")): x for x in rows if isinstance(x, dict)}
    written: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for row in links:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("pointId") or "").strip()
        if not pid:
            continue
        pr = by_id.get(pid)
        if not pr:
            errors.append({"pointId": pid, "detail": "point not in database"})
            continue
        if not pr.get("commandable"):
            errors.append({"pointId": pid, "detail": "not commandable"})
            continue
        oi = str(pr.get("objectIdentifier") or "").strip().lower()
        if not (oi.startswith("binary-value") or oi.startswith("binary-output")):
            errors.append({"pointId": pid, "detail": f"not a binary point: {oi}"})
            continue
        di = int(pr.get("deviceInstance") or 0)
        oi_full = str(pr.get("objectIdentifier") or "")
        if not di or not oi_full:
            errors.append({"pointId": pid, "detail": "missing device_instance or object_identifier"})
            continue
        try:
            rpc_client.client_write_property(di, oi_full, occ, "present-value", priority=8)
            written.append({"pointId": pid, "deviceInstance": di, "objectIdentifier": oi_full, "value": occ})
        except Exception as exc:  # noqa: BLE001
            errors.append({"pointId": pid, "detail": str(exc)})
    return {**status, "written": written, "errors": errors, "ok": len(errors) == 0}
