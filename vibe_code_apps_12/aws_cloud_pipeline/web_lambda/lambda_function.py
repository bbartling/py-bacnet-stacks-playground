"""
Lambda Function URL: dashboard + Bake-a-Py rule lab (static assets in templates/ and static/).
"""

from __future__ import annotations

import base64
import copy
import hashlib
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
    DEFAULT_ROLLING_AVG_MINUTES,
    GO_LIVE_BATCH_HOURS,
    GO_LIVE_MAX_LOOKBACK_HOURS,
    GO_LIVE_OVERLAP_MINUTES,
    NUMPY_AVAILABLE,
    ROLLING_AVG_MINUTES_ALLOWED,
    aux_series_from_rows,
    build_readings_csv,
    chunked_evaluate_custom_rules,
    downsample_aligned_series,
    evaluate_rules_on_readings,
    evaluate_rules_on_readings_chunked,
    eval_rows_preview,
    fault_analytics_from_series,
    lint_python,
    normalize_rolling_avg_minutes,
    prepare_rows_for_evaluate,
    readings_to_rows,
    slim_fdd_summary,
    sweep_rule,
)
from afdd_logging import AfddLog, debug_payload
from rules_defaults import (
    chart_guides_from_rules,
    default_custom_rules,
    get_config_field_meta,
    rules_meta,
    rules_to_panels,
)
from units import TEMP_UNITS, normalize_temp_unit
from brick_fdd_runner import run_brick_scoped_rules
from brick_scope_options import brick_scope_options
from data_model_api import handle_data_model, sync_all_ttl
from model_store import ModelStore
from brick_model import (
    empty_graph,
    graph_from_point_registry,
)
from timeseries import DynamoTimeSeriesStore, align_series_windows
from web_auth import (
    auth_enabled,
    check_credentials,
    extract_bearer,
    issue_token,
    verify_token,
)

TABLE_NAME = os.environ.get("TABLE_NAME", "vibe12-telemetry")
from mqtt_routing import PLATFORM_META_ID
READINGS_LIMIT = int(os.environ.get("READINGS_LIMIT", "62000"))
CHART_RESPONSE_MAX = int(os.environ.get("CHART_RESPONSE_MAX", "5000"))
CHART_CHUNKED_HOURS = float(os.environ.get("CHART_CHUNKED_HOURS", "48"))
CHART_CHUNKED_SAMPLES = int(os.environ.get("CHART_CHUNKED_SAMPLES", "8000"))
DEFAULT_HOURS = int(os.environ.get("DEFAULT_HOURS", "168"))
TEST_HOURS_DEFAULT = int(os.environ.get("TEST_HOURS_DEFAULT", "2"))
FDD_CONFIG_TS = -1
FDD_CUSTOM_RULES_TS = -2
FDD_AFDD_STATE_TS = -3
# Scheduled FDD uses same batch size as go-live unless env overrides.
FDD_CHUNK_HOURS = float(os.environ.get("FDD_CHUNK_HOURS", str(GO_LIVE_BATCH_HOURS)))
_ROOT = Path(__file__).resolve().parent
_SPA_ROOT = _ROOT / "static" / "app"

_MIME = {
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".map": "application/json",
}
_TEXT_SUFFIXES = {".html", ".css", ".js", ".mjs", ".json", ".svg", ".map"}

_table = boto3.resource("dynamodb").Table(TABLE_NAME)
_ts_store = DynamoTimeSeriesStore(_table, read_limit=READINGS_LIMIT)


def _json_safe(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, list):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    return obj


def _response(
    status: int,
    body,
    content_type: str = "application/json",
    *,
    cache_control: str | None = None,
    is_base64: bool = False,
):
    if content_type == "application/json":
        body_out = json.dumps(body)
        is_base64 = False
    else:
        body_out = body
    headers = {"Content-Type": content_type}
    headers["Cache-Control"] = cache_control or ("no-store" if status != 200 else "no-store")
    if cache_control:
        headers["Cache-Control"] = cache_control
    out: dict[str, Any] = {"statusCode": status, "headers": headers, "body": body_out}
    if is_base64:
        out["isBase64Encoded"] = True
    return out


def _unauthorized() -> dict:
    return _response(401, {"error": "unauthorized", "hint": "POST /api/auth/login or send Bearer token"})


def _parse_body(event) -> dict:
    body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        import base64

        body = base64.b64decode(body).decode("utf-8")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {}


def _serve_bytes(path: Path, cache_control: str | None = None) -> dict:
    suffix = path.suffix.lower()
    ctype = _MIME.get(suffix, "application/octet-stream")
    data = path.read_bytes()
    if suffix in _TEXT_SUFFIXES:
        return _response(200, data.decode("utf-8"), ctype, cache_control=cache_control)
    return _response(
        200,
        base64.b64encode(data).decode("ascii"),
        ctype,
        cache_control=cache_control,
        is_base64=True,
    )


def _serve_file(rel: str) -> dict:
    path = (_ROOT / rel).resolve()
    if not str(path).startswith(str(_ROOT)) or not path.is_file():
        return _response(404, {"error": "not found"})
    return _serve_bytes(path)


def _serve_spa(rel: str) -> dict:
    """Serve built React app from static/app (Vite dist)."""
    clean = rel.lstrip("/") or "index.html"
    if ".." in clean.split("/"):
        return _response(404, {"error": "not found"})
    path = (_SPA_ROOT / clean).resolve()
    if not str(path).startswith(str(_SPA_ROOT.resolve())):
        return _response(404, {"error": "not found"})
    if path.is_file():
        cc = "public, max-age=31536000, immutable" if "/assets/" in clean else "no-cache"
        return _serve_bytes(path, cache_control=cc)
    index = _SPA_ROOT / "index.html"
    if index.is_file():
        return _serve_bytes(index, cache_control="no-cache")
    return _response(404, {"error": "spa not built — run scripts/build_web_ui.sh"})


def _api_requires_auth(path: str, method: str) -> bool:
    if not auth_enabled():
        return False
    if path.startswith("/api/auth/"):
        return False
    if path.startswith("/api/health") and method == "GET":
        return False
    return path.startswith("/api/")


def _check_api_auth(event, path: str, method: str) -> dict | None:
    if not _api_requires_auth(path, method):
        return None
    claims = verify_token(extract_bearer(event))
    if claims:
        return None
    return _unauthorized()


def _get_hours(event, default: int | None = None) -> int:
    default = default if default is not None else DEFAULT_HOURS
    try:
        q = event.get("queryStringParameters") or {}
        return max(1, min(168, int(q.get("hours", default))))
    except (TypeError, ValueError):
        return default


def _rolling_minutes_from_body(body: dict, rule: dict | None = None) -> int:
    if body.get("rolling_avg_minutes") is not None:
        return normalize_rolling_avg_minutes(body["rolling_avg_minutes"])
    cfg = (rule or {}).get("config") or {}
    if cfg.get("rolling_avg_minutes") is not None:
        return normalize_rolling_avg_minutes(cfg["rolling_avg_minutes"])
    return DEFAULT_ROLLING_AVG_MINUTES


def _get_display_temp_unit(event, default: str | None = None) -> str:
    default = normalize_temp_unit(default)
    try:
        q = event.get("queryStringParameters") or {}
        if q.get("temp_unit") is not None:
            return normalize_temp_unit(q["temp_unit"])
    except (TypeError, ValueError):
        pass
    return default


def _get_rolling_avg_minutes(event, default: int | None = None) -> int:
    default = default if default is not None else DEFAULT_ROLLING_AVG_MINUTES
    try:
        q = event.get("queryStringParameters") or {}
        if q.get("rolling_avg_minutes") is not None:
            return normalize_rolling_avg_minutes(q["rolling_avg_minutes"])
    except (TypeError, ValueError):
        pass
    return default


def _get_fault_rule_ids(event) -> list[str] | None:
    q = event.get("queryStringParameters") or {}
    if "fault_rules" not in q:
        return None
    raw = q.get("fault_rules") or ""
    if not str(raw).strip():
        return []
    return [s.strip() for s in str(raw).split(",") if s.strip()]


def _wants_csv_export(event) -> bool:
    q = event.get("queryStringParameters") or {}
    fmt = str(q.get("format") or "").lower()
    if fmt in ("csv", "text/csv"):
        return True
    path = event.get("rawPath") or event.get("path") or ""
    return str(path).endswith(".csv")


def _readings_eval_bundle(
    site_id: str,
    building_id: str,
    hours: int,
    rolling_avg_minutes: int = DEFAULT_ROLLING_AVG_MINUTES,
    display_temp_unit: str = "imperial",
    log: AfddLog | None = None,
) -> dict[str, Any]:
    """Fetch readings and evaluate custom rules at full resolution (for chart + CSV)."""
    log = log or AfddLog()
    t0 = time.perf_counter()
    rules = _load_custom_rules()
    log.info(
        f"readings {site_id}/{building_id} hours={hours} "
        f"roll_min={rolling_avg_minutes} rules={len(rules)}"
    )

    readings, point = _fetch_building_readings(site_id, building_id, hours)
    n = len(readings)
    log.info(f"fetched {n} samples in {int((time.perf_counter() - t0) * 1000)}ms")

    rows = readings_to_rows(readings) if readings else []
    minutes = normalize_rolling_avg_minutes(rolling_avg_minutes)
    fdd_status = _fetch_fdd_status()

    use_chunked = bool(readings) and (n > CHART_CHUNKED_SAMPLES or hours > CHART_CHUNKED_HOURS)
    if readings:
        if use_chunked:
            log.info(
                f"chart eval chunked: hours={hours} samples={n} "
                f"chunk_h={GO_LIVE_BATCH_HOURS} overlap={GO_LIVE_OVERLAP_MINUTES}m"
            )
            flag_series, rows = evaluate_rules_on_readings_chunked(
                rules,
                readings,
                chunk_hours=GO_LIVE_BATCH_HOURS,
                overlap_minutes=GO_LIVE_OVERLAP_MINUTES,
                default_rolling_avg_minutes=minutes,
                display_temp_unit=display_temp_unit,
            )
        else:
            if rows:
                prepare_rows_for_evaluate(rows, minutes, temp_unit=display_temp_unit)
            flag_series, rows = evaluate_rules_on_readings(
                rules, readings, rows=rows, default_rolling_avg_minutes=minutes
            )
    else:
        flag_series, rows = {}, rows
        log.warn("no readings in window — chart empty")

    fault_plots_full = {k: flag_series.get(k, [0] * n) for k in flag_series}
    aux_full = aux_series_from_rows(rows) if rows else {}
    ms = int((time.perf_counter() - t0) * 1000)
    log.info(
        f"eval_pts={n} eval_ms={ms} fault_rules={len(fault_plots_full)} chunked={use_chunked}"
    )
    return {
        "rules": rules,
        "readings": readings,
        "rows": rows,
        "minutes": minutes,
        "n": n,
        "fault_plots_full": fault_plots_full,
        "aux_full": aux_full,
        "use_chunked": use_chunked,
        "fdd_status": fdd_status,
        "eval_ms": ms,
        "log": log,
        "site_id": site_id,
        "building_id": building_id,
        "series_id": (point or {}).get("series_id"),
    }


def _sample_to_chart_reading(sample: dict, point: dict | None = None) -> dict | None:
    ts_ms = sample.get("ts_ms")
    if ts_ms is None or int(ts_ms) <= 0:
        return None
    ts_ms = int(ts_ms)
    ts_iso = sample.get("ts") or sample.get("ts_iso") or ""
    if not ts_iso:
        ts_iso = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
    if "degF" in sample and "degC" in sample:
        deg_f = float(sample["degF"])
        deg_c = float(sample["degC"])
    else:
        val = sample.get("value")
        if val is None:
            return None
        deg_f = float(val)
        unit = (sample.get("unit") or (point or {}).get("unit") or "").lower()
        if "celsius" in unit or unit in ("c", "degc", "°c"):
            deg_c = deg_f
            deg_f = deg_c * 9 / 5 + 32
        else:
            deg_c = (deg_f - 32) * 5 / 9
    return {
        "ts_ms": ts_ms,
        "ts_iso": str(ts_iso),
        "degF": deg_f,
        "degC": deg_c,
        "seq": sample.get("seq"),
        "source": sample.get("source", "bacnet"),
        "series_id": sample.get("series_id"),
    }


def _pick_dashboard_point(points: list[dict]) -> dict | None:
    if not points:
        return None
    zat = [p for p in points if p.get("brick_class") == "Zone_Air_Temperature_Sensor"]
    return (zat or points)[0]


def _get_site_building_from_event(event) -> tuple[str, str]:
    q = event.get("queryStringParameters") or {}
    site_id = str(q.get("site_id") or "").strip()
    building_id = str(q.get("building_id") or "").strip()
    return site_id, building_id


def _fetch_building_readings(site_id: str, building_id: str, hours: int) -> tuple[list[dict], dict | None]:
    points = _ts_store.list_points(site_id, building_id)
    point = _pick_dashboard_point(points)
    if not point or not point.get("series_id"):
        return [], None
    raw = _ts_store.get_series(point["series_id"], hours=hours)
    readings = []
    for s in raw:
        row = _sample_to_chart_reading(s, point)
        if row:
            readings.append(row)
    return readings, point


def _fetch_building_readings_between(
    site_id: str,
    building_id: str,
    start_ms: int,
    end_ms_exclusive: int,
) -> list[dict]:
    hours = max(1, int((end_ms_exclusive - start_ms) / 3600000) + 1)
    readings, _ = _fetch_building_readings(site_id, building_id, hours)
    return [r for r in readings if start_ms <= int(r["ts_ms"]) < end_ms_exclusive]


def _rules_revision(rules: list[dict[str, Any]]) -> str:
    raw = json.dumps(rules, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _load_afdd_state() -> dict[str, Any]:
    try:
        resp = _table.get_item(Key={"device_id": PLATFORM_META_ID, "ts_ms": FDD_AFDD_STATE_TS})
        item = _json_safe(resp.get("Item") or {})
        raw = item.get("state_json")
        if raw:
            return json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        pass
    return {}


def _save_afdd_state(state: dict[str, Any]) -> None:
    _table.put_item(
        Item={
            "device_id": PLATFORM_META_ID,
            "ts_ms": FDD_AFDD_STATE_TS,
            "record_type": "afdd_state",
            "state_json": json.dumps(state),
            "watermark_ms": int(state.get("watermark_ms", 0)),
            "rules_revision": state.get("rules_revision", ""),
            "updated_at": int(time.time()),
            "expires_at": int(time.time()) + 30 * 86400,
        }
    )


def _normalize_rules_list(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deep-copy so brick_scope/config are not shared across rules in memory."""
    return copy.deepcopy(rules)


def _load_custom_rules_record() -> tuple[list[dict[str, Any]], str, int | None]:
    try:
        resp = _table.get_item(Key={"device_id": PLATFORM_META_ID, "ts_ms": FDD_CUSTOM_RULES_TS})
        item = _json_safe(resp.get("Item") or {})
        raw = item.get("rules_json")
        if raw:
            data = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(data, list) and data:
                updated = item.get("updated_at")
                return _normalize_rules_list(data), "dynamodb", int(updated) if updated is not None else None
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return _normalize_rules_list(default_custom_rules()), "defaults", None


def _load_custom_rules() -> list[dict[str, Any]]:
    rules, _, _ = _load_custom_rules_record()
    return rules


def _save_custom_rules(rules: list[dict[str, Any]]) -> int:
    updated_at = int(time.time())
    _table.put_item(
        Item={
            "device_id": PLATFORM_META_ID,
            "ts_ms": FDD_CUSTOM_RULES_TS,
            "record_type": "fdd_custom_rules",
            "rules_json": json.dumps(rules),
            "updated_at": updated_at,
            "expires_at": updated_at + 30 * 86400,
        }
    )
    return updated_at


def _fetch_fdd_status() -> dict:
    resp = _table.get_item(Key={"device_id": PLATFORM_META_ID, "ts_ms": 0})
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


def _write_fdd_summary(
    rules: list[dict[str, Any]],
    *,
    site_id: str,
    building_id: str,
    log: AfddLog | None = None,
) -> dict:
    """
    Go live / backfill: always 6 h batches over max 7 d (hard-coded).
    Rule Lab Test rule uses its own hours dropdown — does not change this.
    """
    log = log or AfddLog()
    hours = float(GO_LIVE_MAX_LOOKBACK_HOURS)
    chunk_h = float(GO_LIVE_BATCH_HOURS)
    rev = _rules_revision(rules)
    log.info(
        f"go-live start lookback={hours}h batch={chunk_h}h (hard-coded) rules_rev={rev}"
    )

    def fetch_interval(start_ms: int, end_ms_exclusive: int) -> list[dict]:
        return _fetch_building_readings_between(site_id, building_id, start_ms, end_ms_exclusive)

    try:
        summary = chunked_evaluate_custom_rules(
            rules=rules,
            lookback_hours=hours,
            fetch_interval=fetch_interval,
            chunk_hours=chunk_h,
            overlap_minutes=GO_LIVE_OVERLAP_MINUTES,
        )
    except Exception as exc:
        log.error("chunked_evaluate_custom_rules failed", exc)
        raise

    log.extend(summary.get("eval_log") or [])
    chunk_errors = summary.get("chunk_errors") or []
    if chunk_errors:
        for ce in chunk_errors[:10]:
            log.warn(ce)

    summary["rules_revision"] = rev
    summary["server_log"] = log.snapshot()
    active_flags = summary.get("active_flags") or []
    log.info(
        f"go-live done status={summary.get('fdd_status')} samples={summary.get('sample_count')} "
        f"chunks={summary.get('chunk_count')} flagged_sum={sum((summary.get('flag_counts') or {}).values())}"
    )

    afdd_state = {
        "watermark_ms": summary.get("watermark_ms"),
        "lookback_hours": hours,
        "rules_revision": rev,
        "flag_counts": summary.get("flag_counts") or {},
        "chunk_hours": chunk_h,
        "go_live_batch_hours": GO_LIVE_BATCH_HOURS,
        "go_live_max_hours": GO_LIVE_MAX_LOOKBACK_HOURS,
        "chunk_count": summary.get("chunk_count", 0),
        "last_evaluated_at": summary.get("evaluated_at"),
    }
    _save_afdd_state(afdd_state)
    log.info("afdd_state saved ts_ms=-3")

    db_summary = slim_fdd_summary(summary)
    try:
        _table.put_item(
            Item={
                "device_id": PLATFORM_META_ID,
                "ts_ms": 0,
                "record_type": "fdd_status",
                "fdd_status": db_summary["fdd_status"],
                "active_flags": ",".join(active_flags),
                "summary_json": json.dumps(db_summary),
                "sample_count": summary.get("sample_count", 0),
                "updated_at": int(time.time()),
                "expires_at": int(time.time()) + 30 * 86400,
            }
        )
    except Exception as exc:
        log.error("DynamoDB put_item fdd_status failed", exc)
        raise

    log.info("fdd_status saved ts_ms=0")
    db_summary["server_log"] = log.snapshot()
    return db_summary


def _readings_payload(
    site_id: str,
    building_id: str,
    hours: int,
    rolling_avg_minutes: int = DEFAULT_ROLLING_AVG_MINUTES,
    display_temp_unit: str = "imperial",
    log: AfddLog | None = None,
) -> dict:
    log = log or AfddLog()
    stage = "init"
    try:
        stage = "evaluate"
        bundle = _readings_eval_bundle(
            site_id, building_id, hours, rolling_avg_minutes, display_temp_unit, log=log
        )
        rules = bundle["rules"]
        readings = bundle["readings"]
        rows = bundle["rows"]
        minutes = bundle["minutes"]
        n = bundle["n"]
        fault_plots_full = bundle["fault_plots_full"]
        aux_full = bundle["aux_full"]
        use_chunked = bundle["use_chunked"]
        fdd_status = bundle["fdd_status"]
        ms = bundle["eval_ms"]
        latest = readings[-1] if readings else None

        fault_totals = {k: sum(v) for k, v in fault_plots_full.items()}
        fault_analytics = fault_analytics_from_series(fault_plots_full, rows, rules)

        stage = "downsample_chart"
        chart_readings, chart_plots, chart_aux, chart_stride, truncated = downsample_aligned_series(
            n,
            CHART_RESPONSE_MAX,
            readings,
            fault_plots_full,
            aux_full,
        )
        log.info(
            f"chart_pts={len(chart_readings)}/{n} truncated={truncated} "
            f"eval_ms={ms} fault_rules={len(fault_plots_full)}"
        )
        if truncated:
            log.warn(f"response downsampled to {CHART_RESPONSE_MAX} points for Lambda URL size")

        stage = "done"
    except Exception as exc:
        log.error(f"readings failed at stage={stage}", exc)
        raise

    return {
        "site_id": site_id,
        "building_id": building_id,
        "series_id": bundle.get("series_id"),
        "hours": hours,
        "rolling_avg_minutes": minutes,
        "rolling_avg_minutes_allowed": list(ROLLING_AVG_MINUTES_ALLOWED),
        "count": n,
        "chart_stride": chart_stride,
        "chart_truncated": truncated,
        "chart_max_points": CHART_RESPONSE_MAX,
        "chart_eval_chunked": use_chunked if readings else False,
        "latest": latest,
        "readings": chart_readings,
        "aux_series": chart_aux,
        "fdd_open": fdd_status,
        "fault_panels": rules_to_panels(rules),
        "rules_meta": rules_meta(rules),
        "display_temp_unit": display_temp_unit,
        "temp_units_allowed": list(TEMP_UNITS),
        "chart_guides": chart_guides_from_rules(rules, display_temp_unit),
        "eval_rows_preview": eval_rows_preview(rows),
        "numpy_available": NUMPY_AVAILABLE,
        "fault_plots": chart_plots,
        "fault_totals": fault_totals,
        "fault_analytics": fault_analytics,
        "custom_rules_active": True,
        "debug": debug_payload(
            log,
            stage=stage,
            readings_count=n,
            chart_points_returned=len(chart_readings),
            eval_ms=ms,
            fdd_status=fdd_status.get("fdd_status"),
            fdd_eval_log=(fdd_status.get("eval_log") or [])[-15:],
            afdd_format=fdd_status.get("afdd_format"),
            chunk_count=fdd_status.get("chunk_count"),
            has_1min_avg=bool(rows and "degF_rolling_avg" in rows[0]),
        ),
    }


def _health_payload() -> dict:
    return {
        "status": "ok",
        "app": "vibe12-web",
        "table": TABLE_NAME,
        "mqtt_topic_pattern": "vibe12/{site_id}/{building_id}/{system_id}/{point_id}/telemetry",
        "test_hours_default": TEST_HOURS_DEFAULT,
        "backfill_hours_max": DEFAULT_HOURS,
        "deploy_revision": os.environ.get("DEPLOY_REVISION", ""),
        "modes": {
            "test_rule": f"Query last 1–{DEFAULT_HOURS}h, no FDD status write",
            "save_draft": "Writes rules to DynamoDB ts_ms=-2 only",
            "go_live": f"Rules + backfill {GO_LIVE_BATCH_HOURS}h batches × max {GO_LIVE_MAX_LOOKBACK_HOURS}h (7 d) → ts_ms=0",
        },
        "row_fields": [
            "degF",
            "degF_raw",
            "degF_rolling_avg",
            "temp",
            "temp_raw",
            "temp_rolling_avg",
            "temp_unit",
            "sample_period_ms",
            "rolling_avg_minutes",
            "rolling_window_ms",
            "samples_in_avg",
            "degC",
            "ts_ms",
            "ts",
            "row",
        ],
        "rolling_avg_minutes_allowed": list(ROLLING_AVG_MINUTES_ALLOWED),
        "rolling_avg_minutes_default": DEFAULT_ROLLING_AVG_MINUTES,
        "temp_unit_default": normalize_temp_unit(None),
        "temp_units_allowed": list(TEMP_UNITS),
        "numpy_available": NUMPY_AVAILABLE,
        "sandbox_imports": ["math", "datetime", "numpy (if numpy_available)"],
        "go_live_batch_hours": GO_LIVE_BATCH_HOURS,
        "go_live_max_hours": GO_LIVE_MAX_LOOKBACK_HOURS,
        "fdd_chunk_hours": FDD_CHUNK_HOURS,
        "chart_response_max": CHART_RESPONSE_MAX,
        "chart_chunked_hours": CHART_CHUNKED_HOURS,
        "chart_chunked_samples": CHART_CHUNKED_SAMPLES,
        "mqtt_topic_prefix": "vibe12",
        "features": ["brick_model", "multi_series", "bacnet_ingest", "data_model", "brick_scoped_fdd"],
        "note": "math and datetime always available; import numpy as np when numpy_available",
    }


def lambda_handler(event, context):
    path = event.get("rawPath") or event.get("path") or "/"
    method = (event.get("requestContext", {}).get("http", {}).get("method") or "GET").upper()

    auth_block = _check_api_auth(event, path, method)
    if auth_block is not None:
        return auth_block

    if path == "/api/auth/login" and method == "POST":
        body = _parse_body(event)
        user = str(body.get("username") or "").strip()
        password = str(body.get("password") or "")
        if not check_credentials(user, password):
            print(f"[vibe12] auth failed user={user!r}")
            return _response(401, {"error": "invalid credentials"})
        token = issue_token(user or _USER or "engineer")
        print(f"[vibe12] auth ok user={user}")
        return _response(
            200,
            {
                "ok": True,
                "token": token,
                "username": user,
                "auth_required": auth_enabled(),
            },
        )

    if path == "/api/auth/me" and method == "GET":
        claims = verify_token(extract_bearer(event))
        if not claims and auth_enabled():
            return _unauthorized()
        return _response(
            200,
            {
                "ok": True,
                "username": (claims or {}).get("sub", ""),
                "auth_required": auth_enabled(),
            },
        )

    if path.startswith("/assets/") or path in ("/favicon.ico", "/vite.svg"):
        return _serve_spa(path.lstrip("/"))

    if path.startswith("/api/health"):
        print(f"[vibe12] health ok table={TABLE_NAME}")
        return _response(200, _health_payload())

    if path.startswith("/static/"):
        return _serve_file(path.lstrip("/"))

    if path.startswith("/api/fdd-rules"):
        if method == "POST":
            body = _parse_body(event)
            rules = body.get("rules")
            if not isinstance(rules, list):
                return _response(400, {"error": "rules must be a list"})
            updated_at = _save_custom_rules(rules)
            print(f"[vibe12] save draft: {len(rules)} rule(s) → ts_ms={FDD_CUSTOM_RULES_TS}")
            return _response(
                200,
                {
                    "ok": True,
                    "count": len(rules),
                    "updated_at": updated_at,
                    "rules_source": "dynamodb",
                    "note": f"draft only — go-live runs {GO_LIVE_BATCH_HOURS}h batches × {GO_LIVE_MAX_LOOKBACK_HOURS}h",
                },
            )
        rules, rules_source, updated_at = _load_custom_rules_record()
        display_unit = _get_display_temp_unit(event)
        q = event.get("queryStringParameters") or {}
        site_id = str(q.get("site_id") or "").strip()
        building_id = str(q.get("building_id") or "").strip()
        brick_scope = {"equipment": [], "points": [], "has_data": False, "registry_point_count": 0}
        if site_id and building_id:
            reg_pts = _ts_store.list_points(site_id, building_id)
            model = ModelStore(_ts_store).load_or_bootstrap(site_id, building_id)
            brick_scope = brick_scope_options(reg_pts, model)
        payload: dict[str, Any] = {
            "rules": rules,
            "defaults": _normalize_rules_list(default_custom_rules()),
            "rules_source": rules_source,
            "updated_at": updated_at,
            "config_field_meta": get_config_field_meta(display_unit),
            "temp_unit_default": normalize_temp_unit(None),
            "temp_units_allowed": list(TEMP_UNITS),
            "brick_scope_options": brick_scope,
        }
        return _response(200, payload)

    if path.startswith("/api/playground/lint") and method == "POST":
        code = _parse_body(event).get("code", "")
        return _response(200, lint_python(code if isinstance(code, str) else ""))

    if path.startswith("/api/playground/test-rule") and method == "POST":
        body = _parse_body(event)
        rule = body.get("rule")
        if not isinstance(rule, dict):
            return _response(400, {"error": "rule object required"})
        site_id = str(body.get("site_id") or "").strip()
        building_id = str(body.get("building_id") or "").strip()
        if not site_id or not building_id:
            return _response(400, {"error": "site_id and building_id required"})
        hours = max(1, min(168, int(body.get("hours", TEST_HOURS_DEFAULT))))
        readings, _ = _fetch_building_readings(site_id, building_id, hours)
        print(
            f"[vibe12] test-rule {site_id}/{building_id} hours={hours} "
            f"rows={len(readings)} (no DB status write)"
        )
        rows = readings_to_rows(readings)
        roll_min = _rolling_minutes_from_body(body, rule)
        verbose = bool(body.get("verbose"))
        t0 = time.perf_counter()
        try:
            flags, events = sweep_rule(
                rule.get("code", ""),
                rule.get("config") or {},
                rows,
                capture_print=True,
                rolling_avg_minutes=roll_min,
            )
            if verbose:
                from playground_core import window_trace_events
                from units import effective_temp_unit

                cfg = rule.get("config") or {}
                trace = window_trace_events(rows, temp_unit=effective_temp_unit(cfg))
                if len(events) >= 2:
                    events = events[:-2] + trace + events[-2:]
                else:
                    events = events + trace
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
                "rolling_avg_minutes": roll_min,
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
        # Go live always backfills 7 d in 6 h batches (ignore body.hours).
        hours = GO_LIVE_MAX_LOOKBACK_HOURS
        site_id = str(body.get("site_id") or "").strip()
        building_id = str(body.get("building_id") or "").strip()
        if not site_id or not building_id:
            return _response(400, {"error": "site_id and building_id required"})
        try:
            _save_custom_rules(rules)
            probe, _ = _fetch_building_readings(site_id, building_id, int(hours))
            if not probe:
                return _response(
                    400,
                    {
                        "error": f"no telemetry for {site_id}/{building_id} in last {hours}h",
                    },
                )
            log = AfddLog()
            try:
                summary = _write_fdd_summary(
                    rules, site_id=site_id, building_id=building_id, log=log
                )
            except Exception as exc:
                log.error("go-live _write_fdd_summary failed", exc)
                return _response(
                    500,
                    {
                        "error": str(exc),
                        "hint": "Chunked backfill failed — see server_log and CloudWatch WebFunction.",
                        "debug": debug_payload(log, stage="go_live_failed"),
                        "trace": traceback.format_exc(),
                    },
                )
            return _response(
                200,
                {
                    "ok": True,
                    "summary": summary,
                    "hours": hours,
                    "debug": debug_payload(log, stage="go_live_ok"),
                },
            )
        except Exception as exc:
            log = AfddLog()
            log.error("go-live handler failed", exc)
            return _response(
                500,
                {
                    "error": str(exc),
                    "hint": "Go live request failed before or during backfill.",
                    "debug": debug_payload(log),
                    "trace": traceback.format_exc(),
                },
            )

    if path.startswith("/api/buildings"):
        buildings = _ts_store.list_buildings()
        return _response(200, {"buildings": buildings})

    if path.startswith("/api/points/"):
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 4:
            site_id, building_id = parts[2], parts[3]
            points = _ts_store.list_points(site_id, building_id)
            return _response(
                200,
                {"site_id": site_id, "building_id": building_id, "points": points},
            )
        return _response(400, {"error": "use /api/points/{site_id}/{building_id}"})

    if path.startswith("/api/data-model/"):
        q = event.get("queryStringParameters") or {}
        body = _parse_body(event) if method in ("POST", "PUT") else {}
        status, payload, ctype = handle_data_model(
            path, method, body, q, _ts_store, _load_custom_rules_record
        )
        if ctype.startswith("text/"):
            return _response(status, payload, content_type=ctype)
        return _response(status, payload)

    if path.startswith("/api/playground/test-brick-rule") and method == "POST":
        body = _parse_body(event)
        rule = body.get("rule")
        if not isinstance(rule, dict):
            return _response(400, {"error": "rule object required"})
        site_id = str(body.get("site_id") or "").strip()
        building_id = str(body.get("building_id") or "").strip()
        if not site_id or not building_id:
            return _response(400, {"error": "site_id and building_id required"})
        hours = max(1, min(168, int(body.get("hours", TEST_HOURS_DEFAULT))))
        model = ModelStore(_ts_store).load_or_bootstrap(site_id, building_id)
        summary = run_brick_scoped_rules(
            model, [rule], _ts_store, site_id, building_id, hours=hours
        )
        return _response(200, {"ok": True, **summary})

    if path.startswith("/api/fdd/brick-results/"):
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 5:
            site_id, building_id = parts[3], parts[4]
            summary = _ts_store.get_brick_fdd_summary(site_id, building_id)
            if summary is None:
                return _response(404, {"error": "no brick FDD summary yet"})
            return _response(200, _json_safe(summary))
        return _response(400, {"error": "use /api/fdd/brick-results/{site_id}/{building_id}"})

    if path.startswith("/api/brick/"):
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 4:
            site_id, building_id = parts[2], parts[3]
            if method == "GET":
                graph = _ts_store.get_brick_graph(site_id, building_id)
                if graph is None:
                    points = _ts_store.list_points(site_id, building_id)
                    graph = graph_from_point_registry(site_id, building_id, points)
                return _response(200, {"graph": _json_safe(graph)})
            if method == "PUT":
                body = _parse_body(event)
                graph = body.get("graph") or body
                if not isinstance(graph, dict):
                    return _response(400, {"error": "graph object required"})
                _ts_store.put_brick_graph(site_id, building_id, graph)
                return _response(200, {"ok": True})
        return _response(400, {"error": "use /api/brick/{site_id}/{building_id}"})

    if path.startswith("/api/series/by-tag"):
        q = event.get("queryStringParameters") or {}
        site_id = q.get("site_id", "")
        building_id = q.get("building_id", "")
        brick_class = q.get("brick_class")
        hours = _get_hours(event, default=24)
        if not site_id or not building_id:
            return _response(400, {"error": "site_id and building_id required"})
        data = _ts_store.query_by_building(
            site_id, building_id, hours=hours, brick_class=brick_class
        )
        ts_sorted, aligned = align_series_windows(data)
        return _response(
            200,
            {
                "site_id": site_id,
                "building_id": building_id,
                "brick_class": brick_class,
                "hours": hours,
                "timestamps_ms": ts_sorted,
                "series": {k: _json_safe(v) for k, v in data.items()},
                "aligned": _json_safe(aligned),
            },
        )

    if path.startswith("/api/series"):
        q = event.get("queryStringParameters") or {}
        hours = _get_hours(event, default=24)
        ids_raw = q.get("series_ids") or q.get("series_id") or ""
        series_ids = [s.strip() for s in ids_raw.split(",") if s.strip()]
        if not series_ids:
            return _response(400, {"error": "series_ids query param required"})
        data = _ts_store.get_multi_series(series_ids, hours=hours)
        ts_sorted, aligned = align_series_windows(data)
        return _response(
            200,
            {
                "hours": hours,
                "series_ids": series_ids,
                "series": {k: _json_safe(v) for k, v in data.items()},
                "timestamps_ms": ts_sorted,
                "aligned": _json_safe(aligned),
            },
        )

    if path.startswith("/api/readings"):
        site_id, building_id = _get_site_building_from_event(event)
        if not site_id or not building_id:
            return _response(
                400,
                {"error": "site_id and building_id query params required"},
            )
        hours = _get_hours(event)
        roll_min = _get_rolling_avg_minutes(event)
        display_unit = _get_display_temp_unit(event)
        log = AfddLog()
        try:
            if _wants_csv_export(event):
                fault_ids = _get_fault_rule_ids(event)
                bundle = _readings_eval_bundle(
                    site_id, building_id, hours, roll_min, display_unit, log=log
                )
                if not bundle["readings"]:
                    return _response(404, {"error": "no readings in window for CSV export"})
                csv_body = build_readings_csv(
                    bundle["readings"],
                    bundle["rows"],
                    bundle["fault_plots_full"],
                    bundle["rules"],
                    fault_rule_ids=fault_ids,
                )
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                fname = f"vibe12_readings_{hours}h_{stamp}.csv"
                return {
                    "statusCode": 200,
                    "headers": {
                        "Content-Type": "text/csv; charset=utf-8",
                        "Content-Disposition": f'attachment; filename="{fname}"',
                        "Cache-Control": "no-store",
                    },
                    "body": csv_body,
                }
            payload = _readings_payload(
                site_id, building_id, hours, roll_min, display_unit, log=log
            )
            body = json.dumps(_json_safe(payload))
            if len(body) > 5_500_000:
                log.error(f"response too large bytes={len(body)}")
                return _response(
                    413,
                    {
                        "error": "response too large for Lambda URL",
                        "hint": f"Try fewer hours (requested {hours}h). "
                        f"Chart cap is {CHART_RESPONSE_MAX} points.",
                        "bytes": len(body),
                        "debug": debug_payload(log),
                    },
                )
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Cache-Control": "no-store",
                },
                "body": body,
            }
        except Exception as exc:
            log.error(f"/api/readings failed hours={hours} roll={roll_min}", exc)
            return _response(
                500,
                {
                    "error": str(exc),
                    "hint": "Often timeout or memory on long history + all rules. "
                    "Try History 24h or 6h; see dashboard log + CloudWatch WebFunction.",
                    "hours": hours,
                    "debug": debug_payload(log, stage="failed"),
                    "trace": traceback.format_exc(),
                },
            )

    if path in ("/", "/index.html", "/login"):
        if (_SPA_ROOT / "index.html").is_file():
            return _serve_spa("index.html")
        return _serve_file("templates/dashboard.html")

    if method == "GET" and not path.startswith("/api/"):
        spa_try = _serve_spa(path.lstrip("/"))
        if spa_try.get("statusCode") != 404:
            return spa_try
        if (_SPA_ROOT / "index.html").is_file():
            return _serve_spa("index.html")

    if (_SPA_ROOT / "index.html").is_file():
        return _serve_spa("index.html")
    return _serve_file("templates/dashboard.html")
