"""
Scheduled FDD on DynamoDB telemetry — custom Python rules (ts_ms=-2) or built-in fdd_rules.
"""

from __future__ import annotations

import json
import os
import time

import boto3
from boto3.dynamodb.conditions import Key

from fdd_rules import evaluate_all
from playground_core import aux_series_from_rows, evaluate_rules_on_readings, readings_to_rows
from rules_defaults import default_custom_rules

TABLE_NAME = os.environ.get("TABLE_NAME", "vibe12-telemetry")
DEVICE_ID = os.environ.get("DEVICE_ID", "bosspi-ds18b20")
LOOKBACK_HOURS = float(os.environ.get("LOOKBACK_HOURS", "168"))
READINGS_LIMIT = int(os.environ.get("READINGS_LIMIT", "62000"))
FDD_CUSTOM_RULES_TS = -2

_table = boto3.resource("dynamodb").Table(TABLE_NAME)


def _load_custom_rules() -> list[dict]:
    try:
        resp = _table.get_item(Key={"device_id": DEVICE_ID, "ts_ms": FDD_CUSTOM_RULES_TS})
        item = resp.get("Item") or {}
        raw = item.get("rules_json")
        if raw:
            data = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(data, list) and data:
                return data
    except (json.JSONDecodeError, TypeError):
        pass
    return default_custom_rules()


def _fetch_readings(hours: float) -> list[dict]:
    cutoff_ms = int((time.time() - hours * 3600) * 1000)
    rows: list[dict] = []
    eks = None
    while len(rows) < READINGS_LIMIT:
        kwargs: dict = {
            "KeyConditionExpression": Key("device_id").eq(DEVICE_ID)
            & Key("ts_ms").gte(cutoff_ms),
            "ScanIndexForward": False,
            "Limit": min(1000, READINGS_LIMIT - len(rows)),
        }
        if eks:
            kwargs["ExclusiveStartKey"] = eks
        resp = _table.query(**kwargs)
        for it in resp.get("Items", []):
            ts_ms = int(it.get("ts_ms", 0))
            if ts_ms <= 0 or "degF" not in it:
                continue
            rows.append(
                {
                    "ts_ms": ts_ms,
                    "degF": float(it["degF"]),
                    "degC": float(it.get("degC", 0)),
                }
            )
        eks = resp.get("LastEvaluatedKey")
        if not eks:
            break
    rows.sort(key=lambda r: r["ts_ms"])
    return rows


def _primary_status(active_flags: list[str]) -> str:
    if not active_flags:
        return "NORMAL"
    return active_flags[0].replace("_flag", "").upper()


def lambda_handler(event, context):
    rules = _load_custom_rules()
    readings = _fetch_readings(LOOKBACK_HOURS)
    use_custom = bool(rules)

    if not readings:
        summary = {
            "fdd_status": "MISSING_DATA",
            "active_flags": [],
            "sample_count": 0,
            "lookback_hours": LOOKBACK_HOURS,
            "eval_log": [f"No telemetry in last {LOOKBACK_HOURS}h"],
            "evaluated_at": int(time.time()),
        }
    elif use_custom:
        flag_series = evaluate_rules_on_readings(rules, readings)
        active_flags: list[str] = []
        flag_counts: dict[str, int] = {}
        eval_log = [
            f"Custom rules: {len(readings)} samples / {LOOKBACK_HOURS}h",
            f"{len([r for r in rules if r.get('enabled', True)])} enabled",
        ]
        for key, series in flag_series.items():
            count = sum(series)
            flag_counts[key] = count
            eval_log.append(f"  {key}: {count} flagged")
            if count > 0:
                active_flags.append(key)
        summary = {
            "fdd_status": _primary_status(active_flags),
            "active_flags": active_flags,
            "flag_counts": flag_counts,
            "sample_count": len(readings),
            "lookback_hours": LOOKBACK_HOURS,
            "custom_rules": True,
            "latest_degF": readings[-1]["degF"],
            "latest_degC": readings[-1]["degC"],
            "ts_ms": [r["ts_ms"] for r in readings],
            "flag_series": flag_series,
            "aux_series": aux_series_from_rows(readings_to_rows(readings)),
            "flag_labels": {r["id"]: r.get("title", r["id"]) for r in rules},
            "eval_log": eval_log,
            "evaluated_at": int(time.time()),
        }
    else:
        deg_f = [r["degF"] for r in readings]
        flag_series = evaluate_all(readings)
        active_flags = []
        flag_counts = {}
        eval_log = [
            f"Built-in fdd_rules: {len(readings)} samples / {LOOKBACK_HOURS}h",
            f"degF {min(deg_f):.2f} .. {max(deg_f):.2f}",
        ]
        for key, series in flag_series.items():
            count = sum(series)
            flag_counts[key] = count
            eval_log.append(f"  {key}: {count}")
            if count > 0:
                active_flags.append(key)
        summary = {
            "fdd_status": _primary_status(active_flags),
            "active_flags": active_flags,
            "flag_counts": flag_counts,
            "sample_count": len(readings),
            "lookback_hours": LOOKBACK_HOURS,
            "ts_ms": [r["ts_ms"] for r in readings],
            "flag_series": flag_series,
            "eval_log": eval_log,
            "evaluated_at": int(time.time()),
        }

    _table.put_item(
        Item={
            "device_id": DEVICE_ID,
            "ts_ms": 0,
            "record_type": "fdd_status",
            "fdd_status": summary["fdd_status"],
            "active_flags": ",".join(summary.get("active_flags", [])),
            "summary_json": json.dumps(summary),
            "sample_count": summary.get("sample_count", 0),
            "updated_at": int(time.time()),
            "expires_at": int(time.time()) + 30 * 86400,
        }
    )
    return summary
