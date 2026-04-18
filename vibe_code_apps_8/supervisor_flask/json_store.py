"""JSON file persistence (learning stack — no database)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

_data_env = os.environ.get("SUPERVISOR_DATA_DIR", "").strip()
DATA_DIR = Path(_data_env).resolve() if _data_env else Path(__file__).resolve().parent / "data"


def _atomic_write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(obj, indent=2, sort_keys=False)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def read_json(name: str, default: Any) -> Any:
    path = DATA_DIR / name
    if not path.is_file():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_json(name: str, obj: Any) -> None:
    _atomic_write(DATA_DIR / name, obj)


def ensure_seed_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    defaults: dict[str, Any] = {
        "users.json": {"items": [{"id": "u1", "name": "operator", "role": "admin"}]},
        "app_settings.json": {
            "siteName": "Edge supervisor (learning)",
            "appTitle": "BAS Lite supervisor",
            "routePrefix": "/api",
            "diyBacnetUrl": os.environ.get("DIY_BACNET_URL", "http://127.0.0.1:5000"),
            "diyScheduleObjectName": os.environ.get("DIY_SCHEDULE_OBJECT_NAME", "WeeklyOccupancy"),
        },
        "discovered_devices.json": {
            "items": [
                {
                    "name": "AHU-1",
                    "status": "online",
                    "pointCount": 48,
                    "lastSeen": "demo",
                    "pollingEnabled": True,
                },
                {
                    "name": "VAV-101",
                    "status": "online",
                    "pointCount": 12,
                    "lastSeen": "demo",
                    "pollingEnabled": True,
                },
            ]
        },
        "discovered_points.json": {
            "items": [
                {
                    "deviceId": "AHU-1",
                    "label": "Supply air temp",
                    "value": 55.2,
                    "units": "°F",
                    "lastUpdated": "demo",
                    "alarmState": "normal",
                },
                {
                    "deviceId": "VAV-101",
                    "label": "Zone temp",
                    "value": 72.0,
                    "units": "°F",
                    "lastUpdated": "demo",
                    "alarmState": "normal",
                },
            ]
        },
        "latest_values.json": {"updatedAt": None, "values": {}},
        "poll_plan.json": {"items": [], "note": "Populate when you add a poller loop."},
        "alarm_history.json": {
            "items": [
                {
                    "message": "Demo alarm (edit alarm_history.json)",
                    "state": "cleared",
                    "severity": "info",
                    "triggeredAt": "2026-01-01 00:00",
                }
            ]
        },
        "notifications.json": {
            "items": [
                {
                    "ts": "2026-01-01 00:00",
                    "channel": "log",
                    "detail": "Supervisor started (seed)",
                }
            ]
        },
        "schedules.json": {
            "schedules": [
                {
                    "id": "default-profile",
                    "name": "Default",
                    "form": {
                        "Sunday": {"noSchedule": True, "start": "08:00", "end": "17:00"},
                        "Monday": {"noSchedule": False, "start": "08:00", "end": "17:00"},
                        "Tuesday": {"noSchedule": False, "start": "08:00", "end": "17:00"},
                        "Wednesday": {"noSchedule": False, "start": "08:00", "end": "17:00"},
                        "Thursday": {"noSchedule": False, "start": "08:00", "end": "17:00"},
                        "Friday": {"noSchedule": False, "start": "08:00", "end": "17:00"},
                        "Saturday": {"noSchedule": True, "start": "08:00", "end": "17:00"},
                    },
                    "bacnetPoints": [
                        {"id": "ahu", "name": "AHU supply air temp", "objectId": "AV:1"},
                        {"id": "vav", "name": "VAV zone flow", "objectId": "AV:2"},
                        {"id": "clg", "name": "Cooling setpoint", "objectId": "AV:3"},
                        {"id": "htg", "name": "Heating setpoint", "objectId": "AV:4"},
                        {"id": "fan", "name": "Supply fan command", "objectId": "BV:1"},
                        {"id": "econ", "name": "Economizer enable", "objectId": "BV:2"},
                    ],
                }
            ],
            "activeScheduleId": "default-profile",
            "holidays": [],
        },
    }
    for fname, payload in defaults.items():
        p = DATA_DIR / fname
        if not p.is_file():
            _atomic_write(p, payload)
