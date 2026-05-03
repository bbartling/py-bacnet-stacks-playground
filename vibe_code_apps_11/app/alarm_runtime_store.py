"""JSON-backed runtime data for alarms (device poll health, offline threshold)."""

from __future__ import annotations

import time
from typing import Any

from . import json_store

RUNTIME_FILE = 'alarm_runtime.json'


def read_runtime() -> dict[str, Any]:
    return json_store.read_json(
        RUNTIME_FILE,
        {'deviceOfflineSec': 300, 'lastDevicePollSuccessTs': {}, 'lastDevicePollBatchTs': {}},
    )


def write_runtime(doc: dict[str, Any]) -> None:
    json_store.write_json(RUNTIME_FILE, doc)


def get_device_offline_sec() -> int:
    doc = read_runtime()
    return max(60, min(int(doc.get('deviceOfflineSec') or 300), 86400))


def set_device_offline_sec(sec: int) -> None:
    doc = read_runtime()
    doc['deviceOfflineSec'] = max(60, min(int(sec), 86400))
    write_runtime(doc)


def touch_device_poll_success(device_instance: int, ts: int | None = None) -> None:
    doc = read_runtime()
    t = int(ts or time.time())
    m = doc.get('lastDevicePollSuccessTs')
    if not isinstance(m, dict):
        m = {}
    m[str(int(device_instance))] = t
    doc['lastDevicePollSuccessTs'] = m
    if 'deviceOfflineSec' not in doc:
        doc['deviceOfflineSec'] = 300
    if 'lastDevicePollBatchTs' not in doc or not isinstance(doc.get('lastDevicePollBatchTs'), dict):
        doc['lastDevicePollBatchTs'] = {}
    write_runtime(doc)


def touch_device_poll_batch(device_instances: set[int], ts: int | None = None) -> None:
    """Record that we attempted a poll for these device instances (read-now batch)."""
    if not device_instances:
        return
    doc = read_runtime()
    t = int(ts or time.time())
    m = doc.get('lastDevicePollBatchTs')
    if not isinstance(m, dict):
        m = {}
    for di in device_instances:
        m[str(int(di))] = t
    doc['lastDevicePollBatchTs'] = m
    if 'deviceOfflineSec' not in doc:
        doc['deviceOfflineSec'] = 300
    if 'lastDevicePollSuccessTs' not in doc or not isinstance(doc.get('lastDevicePollSuccessTs'), dict):
        doc['lastDevicePollSuccessTs'] = {}
    write_runtime(doc)
