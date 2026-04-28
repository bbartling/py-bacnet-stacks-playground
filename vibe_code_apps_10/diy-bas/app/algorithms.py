from __future__ import annotations

import time
from typing import Any

from . import json_store, rpc_client
from .config import settings


def add_notification(channel: str, detail: str) -> None:
    notes = json_store.read_json('notifications.json', {'items': []})
    notes.setdefault('items', []).insert(
        0,
        {'ts': time.strftime('%Y-%m-%d %H:%M:%S'), 'channel': channel, 'detail': detail},
    )
    json_store.write_json('notifications.json', notes)


def active_alarm_count() -> int:
    alarms = json_store.read_json('alarm_history.json', {'items': []})
    return sum(1 for item in alarms.get('items', []) if str(item.get('state', '')).lower() == 'active')


def ping_diy_bacnet() -> tuple[bool, str]:
    try:
        rpc_client.server_hello()
        return True, 'reachable'
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def fetch_hosted_values() -> dict[str, Any]:
    payload = rpc_client.server_read_all_values()
    result = payload.get('result', payload)
    return result if isinstance(result, dict) else {}


def get_shared_outside_air_temp() -> dict[str, Any]:
    values = fetch_hosted_values()
    oat = values.get(settings.shared_outside_air_point)
    rh = values.get('web-weather-relative-humidity')
    dew = values.get('web-weather-dew-point')
    return {
        'ok': True,
        'pointName': settings.shared_outside_air_point,
        'outsideAirTemp': oat,
        'relativeHumidity': rh,
        'dewPoint': dew,
        'sharedWith': [],
    }


def get_test_bench_snapshot() -> dict[str, Any]:
    values = fetch_hosted_values()
    return {
        'ok': True,
        'sharedOutsideAirPoint': settings.shared_outside_air_point,
        'devices': {
            'weatherHost': {
                'dryBulb': values.get(settings.shared_outside_air_point),
                'relativeHumidity': values.get('web-weather-relative-humidity'),
                'dewPoint': values.get('web-weather-dew-point'),
            },
        },
    }
