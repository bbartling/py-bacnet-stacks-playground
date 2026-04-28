"""Map diy-bas schedule JSON ↔ diy-bacnet ``server_update_schedule`` weekly format.

diy-bacnet expects ``weekly_schedule`` as **7 lists** in **Monday → Sunday** order
(see server-rpc.md). The vanilla UI uses Sunday → Saturday — we convert here.
"""

from __future__ import annotations

from typing import Any

# BACnet CSV / server_update_schedule order: Monday index 0 … Sunday index 6.
BACNET_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def _norm_time(t: str) -> str:
    t = (t or "00:00").strip()
    parts = t.split(":")
    if len(parts) == 2:
        h, m = int(parts[0]), int(parts[1])
        return f"{h:02d}:{m:02d}"
    return t[:8] if len(t) >= 5 else "00:00"


def day_to_segments(day_form: dict[str, Any]) -> list[dict[str, Any]]:
    """One day's list of {time, value} for server_update_schedule."""
    if day_form.get("noSchedule"):
        return [{"time": "00:00", "value": 0.0}]
    start = _norm_time(str(day_form.get("start", "08:00")))
    end = _norm_time(str(day_form.get("end", "17:00")))
    if start == end:
        return [{"time": "00:00", "value": 0.0}]
    # Simple occupancy model: 1.0 between start/end, 0.0 otherwise (piecewise).
    return [
        {"time": start, "value": 1.0},
        {"time": end, "value": 0.0},
    ]


def profile_to_weekly_schedule(form: dict[str, Any]) -> list[list[dict[str, Any]]]:
    out: list[list[dict[str, Any]]] = []
    for day in BACNET_ORDER:
        out.append(day_to_segments(form.get(day, {"noSchedule": True})))
    return out


def active_profile_payload(
    schedules_doc: dict[str, Any],
    *,
    object_name: str,
    schedule_default: float = 0.0,
) -> dict[str, Any]:
    """Build ``params.update`` for ``server_update_schedule`` from saved JSON."""
    schedules = schedules_doc.get("schedules") or []
    active_id = schedules_doc.get("activeScheduleId")
    prof = None
    for s in schedules:
        if s.get("id") == active_id:
            prof = s
            break
    if prof is None and schedules:
        prof = schedules[0]
    if prof is None:
        raise ValueError("No schedules in document")
    form = prof.get("form") or {}
    return {
        "name": object_name,
        "schedule_default": schedule_default,
        "weekly_schedule": profile_to_weekly_schedule(form),
    }
