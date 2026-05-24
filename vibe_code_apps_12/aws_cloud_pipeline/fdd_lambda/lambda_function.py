"""
Scheduled FDD on DynamoDB telemetry — chunked AFDD + incremental watermark (ts_ms=-3).
"""

from __future__ import annotations

import hashlib
import json
import os
import time

import boto3
from boto3.dynamodb.conditions import Key

from afdd_logging import AfddLog
from fdd_rules import evaluate_all
from playground_core import (
    GO_LIVE_BATCH_HOURS,
    GO_LIVE_MAX_LOOKBACK_HOURS,
    chunked_evaluate_custom_rules,
    slim_fdd_summary,
)
from rules_defaults import default_custom_rules
from timeseries import DynamoTimeSeriesStore
from model_store import ModelStore
from brick_fdd_runner import run_brick_scoped_rules
from brick_rule_targets import rules_with_brick_scope
from data_model_api import sync_all_ttl

TABLE_NAME = os.environ.get("TABLE_NAME", "vibe12-telemetry")
DEVICE_ID = os.environ.get("DEVICE_ID", "bosspi-ds18b20")
LOOKBACK_HOURS = float(os.environ.get("LOOKBACK_HOURS", str(GO_LIVE_MAX_LOOKBACK_HOURS)))
READINGS_LIMIT = int(os.environ.get("READINGS_LIMIT", "62000"))
FDD_CUSTOM_RULES_TS = -2
FDD_AFDD_STATE_TS = -3
FDD_CHUNK_HOURS = float(os.environ.get("FDD_CHUNK_HOURS", str(GO_LIVE_BATCH_HOURS)))
BRICK_FDD_HOURS = int(os.environ.get("BRICK_FDD_HOURS", "24"))

_table = boto3.resource("dynamodb").Table(TABLE_NAME)
_ts_store = DynamoTimeSeriesStore(_table, default_device_id=DEVICE_ID, read_limit=READINGS_LIMIT)


def _json_safe(obj):
    if isinstance(obj, list):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    return obj


def _normalize_reading(item: dict) -> dict | None:
    ts_ms = item.get("ts_ms")
    if ts_ms is None or int(ts_ms) <= 0:
        return None
    if "degF" not in item:
        return None
    return {
        "ts_ms": int(ts_ms),
        "degF": float(item["degF"]),
        "degC": float(item.get("degC", 0)),
    }


def _fetch_readings_between(start_ms: int, end_ms_exclusive: int) -> list[dict]:
    if end_ms_exclusive <= start_ms:
        return []
    end_inclusive = end_ms_exclusive - 1
    rows: list[dict] = []
    eks = None
    while len(rows) < READINGS_LIMIT:
        kwargs: dict = {
            "KeyConditionExpression": Key("device_id").eq(DEVICE_ID)
            & Key("ts_ms").between(start_ms, end_inclusive),
            "ScanIndexForward": True,
            "Limit": min(1000, READINGS_LIMIT - len(rows)),
        }
        if eks:
            kwargs["ExclusiveStartKey"] = eks
        resp = _table.query(**kwargs)
        for it in resp.get("Items", []):
            row = _normalize_reading(_json_safe(it))
            if row and int(row["ts_ms"]) < end_ms_exclusive:
                rows.append(row)
        eks = resp.get("LastEvaluatedKey")
        if not eks:
            break
    return rows


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


def _rules_revision(rules: list[dict]) -> str:
    raw = json.dumps(rules, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _load_afdd_state() -> dict:
    try:
        resp = _table.get_item(Key={"device_id": DEVICE_ID, "ts_ms": FDD_AFDD_STATE_TS})
        item = resp.get("Item") or {}
        raw = item.get("state_json")
        if raw:
            return json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        pass
    return {}


def _save_afdd_state(state: dict) -> None:
    _table.put_item(
        Item={
            "device_id": DEVICE_ID,
            "ts_ms": FDD_AFDD_STATE_TS,
            "record_type": "afdd_state",
            "state_json": json.dumps(state),
            "watermark_ms": int(state.get("watermark_ms", 0)),
            "rules_revision": state.get("rules_revision", ""),
            "updated_at": int(time.time()),
            "expires_at": int(time.time()) + 30 * 86400,
        }
    )


def _write_summary_item(summary: dict) -> dict:
    db_summary = slim_fdd_summary(summary)
    active = summary.get("active_flags") or []
    _table.put_item(
        Item={
            "device_id": DEVICE_ID,
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
    rev = _rules_revision(rules)
    state = _load_afdd_state()
    now_ms = int(time.time() * 1000)
    window_start_ms = now_ms - int(LOOKBACK_HOURS * 3600 * 1000)

    if not rules:
        readings = _fetch_readings_between(window_start_ms, now_ms)
        if not readings:
            summary = {
                "fdd_status": "MISSING_DATA",
                "active_flags": [],
                "sample_count": 0,
                "lookback_hours": LOOKBACK_HOURS,
                "eval_log": [f"No telemetry in last {LOOKBACK_HOURS}h"],
                "evaluated_at": int(time.time()),
            }
        else:
            flag_series = evaluate_all(readings)
            active_flags = []
            flag_counts = {}
            eval_log = [f"Built-in fdd_rules: {len(readings)} samples / {LOOKBACK_HOURS}h"]
            for key, series in flag_series.items():
                count = sum(series)
                flag_counts[key] = count
                eval_log.append(f"  {key}: {count}")
                if count > 0:
                    active_flags.append(key)
            summary = {
                "fdd_status": active_flags[0].replace("_flag", "").upper()
                if active_flags
                else "NORMAL",
                "active_flags": active_flags,
                "flag_counts": flag_counts,
                "sample_count": len(readings),
                "lookback_hours": LOOKBACK_HOURS,
                "eval_log": eval_log,
                "evaluated_at": int(time.time()),
            }
        _write_summary_item(summary)
        return summary

    incremental = (
        state.get("rules_revision") == rev
        and state.get("watermark_ms")
        and int(state["watermark_ms"]) > window_start_ms
    )

    if incremental:
        start_ms = int(state["watermark_ms"])
        initial_counts = dict(state.get("flag_counts") or {})
        hours = (now_ms - window_start_ms) / 3600000.0
        mode = f"incremental from watermark ({FDD_CHUNK_HOURS}h chunks)"
    else:
        start_ms = window_start_ms
        initial_counts = {}
        hours = LOOKBACK_HOURS
        mode = f"full backfill ({FDD_CHUNK_HOURS}h chunks)"

    def fetch_interval(chunk_start: int, end_ms_exclusive: int) -> list[dict]:
        s = max(chunk_start, start_ms)
        if s >= end_ms_exclusive:
            return []
        return _fetch_readings_between(s, end_ms_exclusive)

    log.info(f"{mode} rules_rev={rev}")

    try:
        summary = chunked_evaluate_custom_rules(
            rules=rules,
            lookback_hours=(now_ms - start_ms) / 3600000.0 if incremental else hours,
            fetch_interval=fetch_interval,
            chunk_hours=FDD_CHUNK_HOURS,
            initial_flag_counts=initial_counts if incremental else None,
            window_start_ms=start_ms,
        )
    except Exception as exc:
        log.error("chunked_evaluate failed", exc)
        raise

    log.extend(summary.get("eval_log") or [])
    for ce in (summary.get("chunk_errors") or [])[:10]:
        log.warn(ce)

    summary["rules_revision"] = rev
    summary["eval_log"] = [mode] + list(summary.get("eval_log") or [])

    _save_afdd_state(
        {
            "watermark_ms": summary.get("watermark_ms", now_ms),
            "lookback_hours": LOOKBACK_HOURS,
            "rules_revision": rev,
            "flag_counts": summary.get("flag_counts") or {},
            "chunk_hours": FDD_CHUNK_HOURS,
            "last_evaluated_at": summary.get("evaluated_at"),
        }
    )
    db = _write_summary_item(summary)
    log.info(
        f"done status={db.get('fdd_status')} samples={summary.get('sample_count')} "
        f"chunks={summary.get('chunk_count')}"
    )

    # TTL sync for all buildings with canonical models
    try:
        ttl_out = sync_all_ttl(_ts_store)
        log.info(f"ttl_sync count={ttl_out.get('count')} errors={len(ttl_out.get('errors') or [])}")
    except Exception as exc:
        log.warn(f"ttl_sync failed: {exc}")

    # Building-scoped BRICK FDD for rules with brick_scope
    scoped = rules_with_brick_scope(rules)
    if scoped:
        buildings = _ts_store.list_buildings_with_model()
        if not buildings:
            buildings = _ts_store.list_buildings()
        for b in buildings:
            sid, bid = b["site_id"], b["building_id"]
            try:
                model = ModelStore(_ts_store).load_or_bootstrap(sid, bid)
                brick_summary = run_brick_scoped_rules(
                    model, rules, _ts_store, sid, bid, hours=BRICK_FDD_HOURS
                )
                _ts_store.put_brick_fdd_summary(sid, bid, brick_summary)
                log.info(
                    f"brick_fdd {sid}/{bid} targets={brick_summary.get('targets_evaluated')} "
                    f"flagged={brick_summary.get('total_flagged')}"
                )
            except Exception as exc:
                log.warn(f"brick_fdd {sid}/{bid} failed: {exc}")

    return summary
