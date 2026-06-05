"""
Scheduled FDD — BRICK-scoped rules per building (DynamoDB telemetry).
"""

from __future__ import annotations

import json
import os
import time

import boto3

from afdd_logging import AfddLog
from mqtt_routing import PLATFORM_META_ID
from open_fdd.playground import slim_fdd_summary
from rules_defaults import default_custom_rules
from timeseries import DynamoTimeSeriesStore
from model_store import ModelStore
from brick_fdd_runner import run_brick_scoped_rules
from brick_rule_targets import rules_with_brick_scope
from data_model_api import sync_all_ttl

TABLE_NAME = os.environ.get("TABLE_NAME", "vibe12-telemetry")
READINGS_LIMIT = int(os.environ.get("READINGS_LIMIT", "62000"))
FDD_CUSTOM_RULES_TS = -2
BRICK_FDD_HOURS = int(os.environ.get("BRICK_FDD_HOURS", "24"))

_table = boto3.resource("dynamodb").Table(TABLE_NAME)
_ts_store = DynamoTimeSeriesStore(_table, read_limit=READINGS_LIMIT)


def _load_custom_rules() -> list[dict]:
    try:
        resp = _table.get_item(
            Key={"device_id": PLATFORM_META_ID, "ts_ms": FDD_CUSTOM_RULES_TS}
        )
        item = resp.get("Item") or {}
        raw = item.get("rules_json")
        if raw:
            data = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(data, list) and data:
                return data
    except (json.JSONDecodeError, TypeError):
        pass
    return default_custom_rules()


def _write_platform_summary(summary: dict) -> dict:
    db_summary = slim_fdd_summary(summary)
    active = summary.get("active_flags") or []
    _table.put_item(
        Item={
            "device_id": PLATFORM_META_ID,
            "ts_ms": 0,
            "record_type": "fdd_status",
            "fdd_status": db_summary["fdd_status"],
            "active_flags": ",".join(active),
            "summary_json": json.dumps(db_summary),
            "sample_count": summary.get("sample_count", 0),
            "updated_at": int(time.time()),
            "expires_at": int(time.time()) + 30 * 86400,
        }
    )
    return db_summary


def lambda_handler(event, context):
    log = AfddLog(prefix="vibe12-fdd")
    rules = _load_custom_rules()
    scoped = rules_with_brick_scope(rules)
    buildings = _ts_store.list_buildings_with_model()
    if not buildings:
        buildings = _ts_store.list_buildings()

    total_flagged = 0
    buildings_run = 0
    eval_log: list[str] = []

    if not buildings:
        summary = {
            "fdd_status": "MISSING_DATA",
            "active_flags": [],
            "sample_count": 0,
            "eval_log": ["No buildings with telemetry yet — publish vibe12/…/telemetry"],
            "evaluated_at": int(time.time()),
        }
        _write_platform_summary(summary)
        return summary

    if not scoped:
        summary = {
            "fdd_status": "PENDING",
            "active_flags": [],
            "sample_count": 0,
            "eval_log": ["No BRICK-scoped rules enabled"],
            "evaluated_at": int(time.time()),
        }
        _write_platform_summary(summary)
        return summary

    for b in buildings:
        sid, bid = b["site_id"], b["building_id"]
        try:
            model = ModelStore(_ts_store).load_or_bootstrap(sid, bid)
            brick_summary = run_brick_scoped_rules(
                model, rules, _ts_store, sid, bid, hours=BRICK_FDD_HOURS
            )
            _ts_store.put_brick_fdd_summary(sid, bid, brick_summary)
            flagged = int(brick_summary.get("total_flagged") or 0)
            total_flagged += flagged
            buildings_run += 1
            eval_log.append(
                f"{sid}/{bid}: targets={brick_summary.get('targets_evaluated')} flagged={flagged}"
            )
            log.info(
                f"brick_fdd {sid}/{bid} targets={brick_summary.get('targets_evaluated')} "
                f"flagged={flagged}"
            )
        except Exception as exc:
            log.warn(f"brick_fdd {sid}/{bid} failed: {exc}")
            eval_log.append(f"{sid}/{bid}: error {exc}")

    try:
        ttl_out = sync_all_ttl(_ts_store)
        log.info(f"ttl_sync count={ttl_out.get('count')} errors={len(ttl_out.get('errors') or [])}")
    except Exception as exc:
        log.warn(f"ttl_sync failed: {exc}")

    summary = {
        "fdd_status": "FAULT" if total_flagged else "NORMAL",
        "active_flags": [],
        "sample_count": buildings_run,
        "buildings_evaluated": buildings_run,
        "total_flagged": total_flagged,
        "eval_log": eval_log,
        "evaluated_at": int(time.time()),
    }
    _write_platform_summary(summary)
    return summary
