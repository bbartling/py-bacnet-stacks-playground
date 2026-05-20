"""
Lambda Function URL: dashboard + Bake-a-Py rule lab (static assets in templates/ and static/).
"""

from __future__ import annotations

import json
import os
import time
import traceback
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from playground_core import (
    aux_series_from_rows,
    evaluate_rules_on_readings,
    lint_python,
    readings_to_rows,
    sweep_rule,
)
from rules_defaults import CONFIG_FIELD_META, default_custom_rules, rules_to_panels

TABLE_NAME = os.environ.get("TABLE_NAME", "vibe12-telemetry")
DEVICE_ID = os.environ.get("DEVICE_ID", "bosspi-ds18b20")
READINGS_LIMIT = int(os.environ.get("READINGS_LIMIT", "62000"))
DEFAULT_HOURS = int(os.environ.get("DEFAULT_HOURS", "168"))
TEST_HOURS_DEFAULT = int(os.environ.get("TEST_HOURS_DEFAULT", "6"))
FDD_CONFIG_TS = -1
FDD_CUSTOM_RULES_TS = -2
_ROOT = Path(__file__).resolve().parent

_MIME = {
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".html": "text/html; charset=utf-8",
}

_table = boto3.resource("dynamodb").Table(TABLE_NAME)


def _json_safe(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, list):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    return obj


def _response(status: int, body, content_type: str = "application/json"):
    if content_type == "application/json":
        body_out = json.dumps(body)
    else:
        body_out = body
    return {
        "statusCode": status,
        "headers": {"Content-Type": content_type, "Cache-Control": "no-store"},
        "body": body_out,
    }


def _parse_body(event) -> dict:
    body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        import base64

        body = base64.b64decode(body).decode("utf-8")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {}


def _serve_file(rel: str) -> dict:
    path = (_ROOT / rel).resolve()
    if not str(path).startswith(str(_ROOT)) or not path.is_file():
        return _response(404, {"error": "not found"})
    return _response(200, path.read_text(encoding="utf-8"), _MIME.get(path.suffix, "text/plain"))


def _get_hours(event, default: int | None = None) -> int:
    default = default if default is not None else DEFAULT_HOURS
    try:
        q = event.get("queryStringParameters") or {}
        return max(1, min(168, int(q.get("hours", default))))
    except (TypeError, ValueError):
        return default


def _normalize_reading(item: dict) -> dict | None:
    ts_ms = item.get("ts_ms")
    if ts_ms is None or int(ts_ms) <= 0:
        return None
    if "degF" not in item or "degC" not in item:
        return None
    ts_ms = int(ts_ms)
    ts_iso = item.get("ts_iso")
    if not ts_iso:
        ts_iso = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
    return {
        "ts_ms": ts_ms,
        "ts_iso": str(ts_iso),
        "degF": float(item["degF"]),
        "degC": float(item["degC"]),
        "seq": item.get("seq"),
        "source": item.get("source"),
    }


def _fetch_readings(hours: int) -> list[dict]:
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
            row = _normalize_reading(_json_safe(it))
            if row:
                rows.append(row)
        eks = resp.get("LastEvaluatedKey")
        if not eks:
            break
    rows.reverse()
    return rows


def _load_custom_rules() -> list[dict[str, Any]]:
    try:
        resp = _table.get_item(Key={"device_id": DEVICE_ID, "ts_ms": FDD_CUSTOM_RULES_TS})
        item = _json_safe(resp.get("Item") or {})
        raw = item.get("rules_json")
        if raw:
            data = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(data, list) and data:
                return data
    except (json.JSONDecodeError, TypeError):
        pass
    return default_custom_rules()


def _save_custom_rules(rules: list[dict[str, Any]]) -> None:
    _table.put_item(
        Item={
            "device_id": DEVICE_ID,
            "ts_ms": FDD_CUSTOM_RULES_TS,
            "record_type": "fdd_custom_rules",
            "rules_json": json.dumps(rules),
            "updated_at": int(time.time()),
            "expires_at": int(time.time()) + 30 * 86400,
        }
    )


def _fetch_fdd_status() -> dict:
    resp = _table.get_item(Key={"device_id": DEVICE_ID, "ts_ms": 0})
    item = _json_safe(resp.get("Item") or {})
    raw = item.get("summary_json")
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return {
        "fdd_status": item.get("fdd_status", "PENDING"),
        "active_flags": [],
        "sample_count": item.get("sample_count", 0),
    }


def _write_fdd_summary(readings: list[dict], rules: list[dict[str, Any]], hours: float) -> dict:
    rows = readings_to_rows(readings)
    flag_series, rows = evaluate_rules_on_readings(rules, readings, rows=rows)
    active_flags: list[str] = []
    flag_counts: dict[str, int] = {}
    flag_labels = {r["id"]: r.get("title", r["id"]) for r in rules if r.get("enabled", True)}
    eval_log = [
        f"Custom rules backfill: {len(readings)} samples over {hours}h",
        f"{len([r for r in rules if r.get('enabled', True)])} enabled rule(s)",
    ]
    for key, series in flag_series.items():
        count = sum(series)
        flag_counts[key] = count
        eval_log.append(f"  {key}: {count} flagged")
        if count > 0:
            active_flags.append(key)

    status = "NORMAL" if not active_flags else active_flags[0].replace("_flag", "").upper()
    summary = {
        "fdd_status": status,
        "active_flags": active_flags,
        "flag_counts": flag_counts,
        "sample_count": len(readings),
        "lookback_hours": hours,
        "custom_rules": True,
        "ts_ms": [r["ts_ms"] for r in readings],
        "flag_series": flag_series,
        "aux_series": aux_series_from_rows(rows),
        "flag_labels": flag_labels,
        "eval_log": eval_log + ["  flags = your evaluate() per row (no backend debounce/avg helpers)"],
        "evaluated_at": int(time.time()),
    }
    if readings:
        summary["latest_degF"] = readings[-1]["degF"]
        summary["latest_degC"] = readings[-1]["degC"]

    _table.put_item(
        Item={
            "device_id": DEVICE_ID,
            "ts_ms": 0,
            "record_type": "fdd_status",
            "fdd_status": summary["fdd_status"],
            "active_flags": ",".join(active_flags),
            "summary_json": json.dumps(summary),
            "sample_count": len(readings),
            "updated_at": int(time.time()),
            "expires_at": int(time.time()) + 30 * 86400,
        }
    )
    return summary


def _readings_payload(hours: int) -> dict:
    rules = _load_custom_rules()
    readings = _fetch_readings(hours)
    rows = readings_to_rows(readings) if readings else []
    fdd_status = _fetch_fdd_status()
    latest = readings[-1] if readings else None
    flag_series, rows = (
        evaluate_rules_on_readings(rules, readings, rows=rows) if readings else ({}, rows)
    )
    fault_plots = {
        k: flag_series.get(k, [0] * len(readings)) for k in flag_series
    }
    return {
        "device_id": DEVICE_ID,
        "hours": hours,
        "count": len(readings),
        "latest": latest,
        "readings": readings,
        "aux_series": aux_series_from_rows(rows),
        "fdd_open": fdd_status,
        "fault_panels": rules_to_panels(rules),
        "fault_plots": fault_plots,
        "fault_totals": {k: sum(v) for k, v in fault_plots.items()},
        "custom_rules_active": True,
        "debug": {
            "readings_count": len(readings),
            "fdd_status": fdd_status.get("fdd_status"),
            "fdd_eval_log": fdd_status.get("eval_log", []),
            "has_1min_avg": bool(rows and "degF_1min_avg" in rows[0]),
        },
    }


def _health_payload() -> dict:
    return {
        "status": "ok",
        "app": "vibe12-web",
        "device_id": DEVICE_ID,
        "table": TABLE_NAME,
        "test_hours_default": TEST_HOURS_DEFAULT,
        "backfill_hours_max": DEFAULT_HOURS,
        "deploy_revision": os.environ.get("DEPLOY_REVISION", ""),
        "modes": {
            "test_rule": f"Query last 1–{DEFAULT_HOURS}h, no FDD status write",
            "save_draft": "Writes rules to DynamoDB ts_ms=-2 only",
            "go_live": f"Rules + backfill up to {DEFAULT_HOURS}h → FDD status ts_ms=0",
        },
        "row_fields": ["degF", "degC", "ts_ms", "ts", "row"],
        "note": "Set degF_1min_avg on rows in your rule code for dashboard avg overlay",
    }


def lambda_handler(event, context):
    path = event.get("rawPath") or event.get("path") or "/"
    method = (event.get("requestContext", {}).get("http", {}).get("method") or "GET").upper()

    if path.startswith("/api/health"):
        print(f"[vibe12] health ok device={DEVICE_ID} table={TABLE_NAME}")
        return _response(200, _health_payload())

    if path.startswith("/static/"):
        return _serve_file(path.lstrip("/"))

    if path.startswith("/api/fdd-rules"):
        if method == "POST":
            body = _parse_body(event)
            rules = body.get("rules")
            if not isinstance(rules, list):
                return _response(400, {"error": "rules must be a list"})
            _save_custom_rules(rules)
            print(f"[vibe12] save draft: {len(rules)} rule(s) → ts_ms={FDD_CUSTOM_RULES_TS}")
            return _response(
                200,
                {"ok": True, "count": len(rules), "note": "draft only — use go-live for 7d backfill"},
            )
        rules = _load_custom_rules()
        return _response(
            200,
            {
                "rules": rules,
                "defaults": default_custom_rules(),
                "config_field_meta": CONFIG_FIELD_META,
            },
        )

    if path.startswith("/api/playground/lint") and method == "POST":
        code = _parse_body(event).get("code", "")
        return _response(200, lint_python(code if isinstance(code, str) else ""))

    if path.startswith("/api/playground/test-rule") and method == "POST":
        body = _parse_body(event)
        rule = body.get("rule")
        if not isinstance(rule, dict):
            return _response(400, {"error": "rule object required"})
        hours = max(1, min(168, int(body.get("hours", TEST_HOURS_DEFAULT))))
        readings = _fetch_readings(hours)
        print(f"[vibe12] test-rule hours={hours} rows={len(readings)} (no DB status write)")
        rows = readings_to_rows(readings)
        t0 = time.perf_counter()
        try:
            flags, events = sweep_rule(
                rule.get("code", ""),
                rule.get("config") or {},
                rows,
                capture_print=True,
            )
        except Exception:
            return _response(
                400,
                {"error": "rule failed", "trace": traceback.format_exc()},
            )
        ms = int((time.perf_counter() - t0) * 1000)
        return _response(
            200,
            {
                "ok": True,
                "hours": hours,
                "rows": len(rows),
                "flagged": sum(flags),
                "events": events,
                "ms": ms,
            },
        )

    if path.startswith("/api/playground/go-live") and method == "POST":
        body = _parse_body(event)
        rules = body.get("rules")
        if not isinstance(rules, list):
            return _response(400, {"error": "rules must be a list"})
        hours = max(1, min(168, int(body.get("hours", DEFAULT_HOURS))))
        _save_custom_rules(rules)
        readings = _fetch_readings(hours)
        if not readings:
            return _response(400, {"error": f"no telemetry in last {hours}h"})
        summary = _write_fdd_summary(readings, rules, float(hours))
        print(
            f"[vibe12] go-live hours={hours} rows={len(readings)} "
            f"status={summary.get('fdd_status')} flags={summary.get('active_flags')}"
        )
        return _response(200, {"ok": True, "summary": summary, "hours": hours})

    if path.startswith("/api/readings"):
        hours = _get_hours(event)
        return _response(200, _readings_payload(hours))

    if path in ("/", "/index.html"):
        return _serve_file("templates/dashboard.html")

    return _serve_file("templates/dashboard.html")
