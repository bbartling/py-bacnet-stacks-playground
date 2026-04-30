"""One-shot legacy JSON -> SQLite migration helpers."""

from __future__ import annotations

import uuid

from . import json_store, trend_store


def migrate_legacy_json_once() -> None:
    polling_doc = json_store.read_json('polling_config.json', {'items': []})
    if isinstance(polling_doc, dict) and isinstance(polling_doc.get('items'), list):
        trend_store.write_polling_config(polling_doc.get('items', []))
    notes_doc = json_store.read_json('device_notes.json', {'items': []})
    if isinstance(notes_doc, dict):
        for row in notes_doc.get('items', []):
            if isinstance(row, dict) and row.get('deviceInstance') is not None:
                trend_store.upsert_device_note(int(row['deviceInstance']), str(row.get('note') or ''))
    layouts_doc = json_store.read_json('dashboard_layouts.json', {'items': []})
    if isinstance(layouts_doc, dict):
        for row in layouts_doc.get('items', []):
            if not isinstance(row, dict):
                continue
            layout_id = str(row.get('id') or uuid.uuid4())
            trend_store.upsert_dashboard_layout(layout_id, str(row.get('name') or 'Overview'), str(row.get('roleScope') or 'all'), row.get('layout') or {})
    rules_doc = json_store.read_json('alarm_rules.json', {'items': []})
    if isinstance(rules_doc, dict):
        for row in rules_doc.get('items', []):
            if isinstance(row, dict) and row.get('pointId'):
                trend_store.upsert_alarm_rule(row)
