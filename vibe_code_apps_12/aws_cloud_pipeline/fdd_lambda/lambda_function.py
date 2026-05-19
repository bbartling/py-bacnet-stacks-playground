"""
Scheduled FDD on DynamoDB telemetry (zip Lambda — no Docker / open-fdd).

Rules: fdd_rules.py; tunables in DynamoDB row ts_ms=-1 (saved from dashboard).
"""

from __future__ import annotations

import json
import os
import time

import boto3
from boto3.dynamodb.conditions import Key

from fdd_rules import DEFAULT_CONFIG, config_from_dict, config_to_dict, evaluate_all

TABLE_NAME = os.environ.get("TABLE_NAME", "vibe12-telemetry")
DEVICE_ID = os.environ.get("DEVICE_ID", "bosspi-ds18b20")
LOOKBACK_HOURS = float(os.environ.get("LOOKBACK_HOURS", "168"))
READINGS_LIMIT = int(os.environ.get("READINGS_LIMIT", "62000"))
FDD_CONFIG_TS = -1

_table = boto3.resource("dynamodb").Table(TABLE_NAME)


def _load_rule_config():
    try:
        resp = _table.get_item(Key={"device_id": DEVICE_ID, "ts_ms": FDD_CONFIG_TS})
        item = resp.get("Item") or {}
        raw = item.get("config_json")
        if raw:
            data = json.loads(raw) if isinstance(raw, str) else raw
            cfg = config_from_dict(data)
            return cfg, config_to_dict(cfg)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return DEFAULT_CONFIG, config_to_dict(DEFAULT_CONFIG)


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
    rule_cfg, rule_cfg_dict = _load_rule_config()
    readings = _fetch_readings(LOOKBACK_HOURS)

    if not readings:
        summary = {
            "fdd_status": "MISSING_DATA",
            "active_flags": [],
            "sample_count": 0,
            "lookback_hours": LOOKBACK_HOURS,
            "rule_config": rule_cfg_dict,
            "eval_log": [f"No telemetry in last {LOOKBACK_HOURS}h"],
            "evaluated_at": int(time.time()),
        }
    else:
        deg_f = [r["degF"] for r in readings]
        rw = rule_cfg.rolling_window
        eval_log = [
            f"Loaded {len(readings)} samples over {LOOKBACK_HOURS}h (pure Python FDD)",
            f"degF range {min(deg_f):.2f} .. {max(deg_f):.2f}",
            f"config bounds {rule_cfg.bounds_low_f}–{rule_cfg.bounds_high_f} °F",
        ]
        flag_series = evaluate_all(readings, rule_cfg)
        active_flags: list[str] = []
        flag_counts: dict[str, int] = {}
        for key, series in flag_series.items():
            count = sum(series)
            flag_counts[key] = count
            eval_log.append(f"  {key}: {count} flagged (rolling_window={rw})")
            if count > 0:
                active_flags.append(key)

        summary = {
            "fdd_status": _primary_status(active_flags),
            "active_flags": active_flags,
            "flag_counts": flag_counts,
            "sample_count": len(readings),
            "lookback_hours": LOOKBACK_HOURS,
            "rule_config": rule_cfg_dict,
            "latest_degF": readings[-1]["degF"],
            "latest_degC": readings[-1]["degC"],
            "ts_ms": [r["ts_ms"] for r in readings],
            "flag_series": flag_series,
            "flag_labels": rule_cfg.flag_labels(),
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
