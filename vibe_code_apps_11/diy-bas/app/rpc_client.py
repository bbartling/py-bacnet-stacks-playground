from __future__ import annotations

import uuid
from typing import Any

import requests

from .config import settings


def call_method(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{settings.diy_bacnet_url}/{method}"
    body = {
        'jsonrpc': '2.0',
        'id': str(uuid.uuid4()),
        'method': method,
        'params': params if params is not None else {},
    }
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    if settings.bacnet_rpc_api_key:
        headers['Authorization'] = f'Bearer {settings.bacnet_rpc_api_key}'
    response = requests.post(url, json=body, headers=headers, timeout=settings.rpc_timeout)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict) and payload.get('error'):
        raise RuntimeError(str(payload['error']))
    return payload if isinstance(payload, dict) else {'result': payload}


def server_hello() -> dict[str, Any]:
    return call_method('server_hello', {})


def server_read_all_values() -> dict[str, Any]:
    return call_method('server_read_all_values', {})


def server_read_schedule(name: str) -> dict[str, Any]:
    return call_method('server_read_schedule', {'request': {'name': name}})


def server_update_schedule(update: dict[str, Any]) -> dict[str, Any]:
    return call_method('server_update_schedule', {'update': update})


def client_read_property(device_instance: int, object_identifier: str, property_identifier: str = 'present-value') -> dict[str, Any]:
    return call_method(
        'client_read_property',
        {
            'request': {
                'device_instance': device_instance,
                'object_identifier': object_identifier,
                'property_identifier': property_identifier,
            }
        },
    )


def client_read_multiple(device_instance: int, requests_list: list[dict[str, str]]) -> dict[str, Any]:
    return call_method(
        'client_read_multiple',
        {'request': {'device_instance': device_instance, 'requests': requests_list}},
    )


def client_whois_range(start_instance: int, end_instance: int) -> dict[str, Any]:
    return call_method(
        'client_whois_range',
        {'request': {'start_instance': int(start_instance), 'end_instance': int(end_instance)}},
    )


def client_point_discovery(device_instance: int) -> dict[str, Any]:
    return call_method(
        'client_point_discovery',
        {'instance': {'device_instance': int(device_instance)}},
    )


def client_write_property(
    device_instance: int,
    object_identifier: str,
    value: Any,
    property_identifier: str = 'present-value',
    priority: int | None = None,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        'device_instance': int(device_instance),
        'object_identifier': object_identifier,
        'property_identifier': property_identifier,
        'value': value,
    }
    if priority is not None:
        request['priority'] = int(priority)
    return call_method('client_write_property', {'request': request})
