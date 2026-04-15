"""Legacy /app8/api/* JSON contract for the BAS Lite React SPA."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import smtplib
import ssl
from collections import defaultdict, deque
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional
from uuid import uuid4

import httpx
from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from easy_aso.bacnet_client.jsonrpc_client import JsonRpcBacnetClient
from easy_aso.supervisor.coordinator import SupervisorCoordinator

logger = logging.getLogger(__name__)

router = APIRouter()

SCHEDULE_PATH = Path(os.environ.get("BAS_LITE_SCHEDULE_PATH", "/data/schedule.json"))
DRIVER_CFG_DIR = Path(os.environ.get("BAS_LITE_DRIVER_CONFIG_DIR", "/data/driver_configs"))
TREND_INTERVAL_SEC = float(os.environ.get("BAS_LITE_TREND_SAMPLE_SEC", "60"))
TREND_MAX = int(os.environ.get("BAS_LITE_TREND_MAX_SAMPLES", "1440"))
ALARM_RULES_PATH = Path(os.environ.get("BAS_LITE_ALARM_RULES_PATH", "/data/alarm_rules.json"))
DISCOVERY_EXPORT_DIR = Path(os.environ.get("BAS_LITE_DISCOVERY_EXPORT_DIR", "/data/discovery_exports"))
ALARM_STATE_PATH = Path(os.environ.get("BAS_LITE_ALARM_STATE_PATH", "/data/alarm_state.json"))
NOTIFICATIONS_CFG_PATH = Path(os.environ.get("BAS_LITE_NOTIFICATIONS_CFG_PATH", "/data/notifications_config.json"))
NOTIFICATIONS_LOG_PATH = Path(os.environ.get("BAS_LITE_NOTIFICATIONS_LOG_PATH", "/data/notifications.log.jsonl"))
COMPOSE_PROJECT_NAME = os.environ.get("COMPOSE_PROJECT_NAME", "bas-lite")

try:
    import docker  # type: ignore
except Exception:  # pragma: no cover
    docker = None


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _coord(request: Request) -> SupervisorCoordinator:
    return request.app.state.coordinator


def _trend_buf(request: Request) -> Dict[str, Deque[dict[str, Any]]]:
    b = getattr(request.app.state, "trend_buffers", None)
    if b is None:
        b = defaultdict(lambda: deque(maxlen=TREND_MAX))
        request.app.state.trend_buffers = b
    return b


def _event_subscribers(app: Any) -> list[asyncio.Queue]:
    subs = getattr(app.state, "event_subscribers", None)
    if subs is None:
        subs = []
        app.state.event_subscribers = subs
    return subs


def _publish_event(app: Any, topic: str, payload: Optional[dict[str, Any]] = None) -> None:
    evt = {"type": "event", "topic": topic, "ts": _utc(), "payload": payload or {}}
    for q in list(_event_subscribers(app)):
        try:
            q.put_nowait(evt)
        except Exception:
            # Drop events for slow/dead consumers; next publish keeps stream healthy.
            continue


def _device_kind(name: str) -> str:
    n = name.lower()
    if "ahu" in n:
        return "ahu"
    if "vav" in n:
        return "vav"
    return "equipment"


def _parse_device_id_numeric(device_address: str) -> int:
    """Best-effort BACnet device instance for UI (bench used small ints)."""
    m = re.search(r"(\d{4,})", device_address)
    if m:
        return int(m.group(1)[:8]) % 10_000_000
    return abs(hash(device_address)) % 9_000_000 + 1_000_000


def _read_json_file(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("failed reading json file: %s", path)
        return default


def _write_json_file(path: Path, body: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")


def _append_notification_log(item: dict[str, Any]) -> None:
    NOTIFICATIONS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NOTIFICATIONS_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item) + "\n")


def _to_float(v: Any) -> Optional[float]:
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v))
    except Exception:
        return None


def _is_truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    s = str(v).strip().lower()
    return s in {"true", "on", "1", "active", "open", "yes"}


def _default_day_block() -> dict[str, Any]:
    return {"occupied": False, "startMinutes": 8 * 60, "endMinutes": 17 * 60}


def _default_weekly() -> dict[str, Any]:
    return {k: _default_day_block() for k in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}


def _normalize_schedule_doc(raw: Any) -> dict[str, Any]:
    # New model: schedules[] with assignments + holidays/date overrides.
    if isinstance(raw, dict) and isinstance(raw.get("schedules"), list):
        out = dict(raw)
        out.setdefault("version", 2)
        out.setdefault("timezone", "local")
        out["hostedScheduleName"] = str(out.get("hostedScheduleName") or "occupancy-schedule").strip() or "occupancy-schedule"
        normalized = []
        for s in out["schedules"]:
            if not isinstance(s, dict):
                continue
            weekly = s.get("weekly", {})
            if not isinstance(weekly, dict):
                weekly = {}
            merged_weekly = _default_weekly()
            for k, v in weekly.items():
                if k in merged_weekly and isinstance(v, dict):
                    merged_weekly[k] = {
                        "occupied": bool(v.get("occupied", False)),
                        "startMinutes": int(v.get("startMinutes", 8 * 60)),
                        "endMinutes": int(v.get("endMinutes", 17 * 60)),
                    }
            bindings_in = s.get("bacnetBindings") if isinstance(s.get("bacnetBindings"), list) else []
            bacnet_bindings: List[dict[str, Any]] = []
            for x in bindings_in:
                if not isinstance(x, dict):
                    continue
                pid = str(x.get("pointId") or "").strip()
                if not pid:
                    continue
                oid = str(x.get("objectId") or "").strip()
                bacnet_bindings.append(
                    {
                        "id": str(x.get("id") or str(uuid4())),
                        "pointId": pid,
                        "name": str(x.get("name") or pid),
                        "objectId": oid or None,
                    }
                )
            normalized.append(
                {
                    "id": str(s.get("id") or f"sched_{uuid4().hex[:8]}"),
                    "label": str(s.get("label") or "Schedule"),
                    "description": str(s.get("description") or ""),
                    "assignments": [str(x) for x in (s.get("assignments") or []) if str(x).strip()],
                    "weekly": merged_weekly,
                    "holidays": [h for h in (s.get("holidays") or []) if isinstance(h, dict)],
                    "bacnetBindings": bacnet_bindings,
                }
            )
        out["schedules"] = normalized
        return out

    # Legacy v1 model migration
    weekly = raw.get("weekly", {}) if isinstance(raw, dict) else {}
    holidays = raw.get("holidays", []) if isinstance(raw, dict) else []
    legacy_links = raw.get("linkedPoints", []) if isinstance(raw, dict) else []
    assignments = []
    if isinstance(legacy_links, list):
        seen = set()
        for lp in legacy_links:
            if isinstance(lp, dict):
                did = str(lp.get("deviceId") or "").strip()
                if did and did not in seen:
                    assignments.append(did)
                    seen.add(did)
    merged_weekly = _default_weekly()
    if isinstance(weekly, dict):
        for k, v in weekly.items():
            if k in merged_weekly and isinstance(v, dict):
                merged_weekly[k] = {
                    "occupied": bool(v.get("occupied", False)),
                    "startMinutes": int(v.get("startMinutes", 8 * 60)),
                    "endMinutes": int(v.get("endMinutes", 17 * 60)),
                }
    return {
        "version": 2,
        "timezone": "local",
        "hostedScheduleName": "occupancy-schedule",
        "schedules": [
            {
                "id": "default",
                "label": str(raw.get("label") or "Default") if isinstance(raw, dict) else "Default",
                "description": "Migrated from legacy single-schedule format",
                "assignments": assignments,
                "weekly": merged_weekly,
                "holidays": holidays if isinstance(holidays, list) else [],
                "bacnetBindings": [],
            }
        ],
    }


def _iso_date_local(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _effective_for_schedule(s: dict[str, Any], now: datetime) -> dict[str, Any]:
    weekly = s.get("weekly", {})
    holidays = s.get("holidays", [])
    day_map = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    day_key = day_map[now.weekday()]
    date_s = _iso_date_local(now)
    mins = now.hour * 60 + now.minute

    override = None
    if isinstance(holidays, list):
        for h in holidays:
            if not isinstance(h, dict):
                continue
            # supports either exact date or start/end
            if h.get("date"):
                if str(h.get("date")) == date_s:
                    override = bool(h.get("occupied", False))
                    break
            else:
                start = str(h.get("start") or "")
                end = str(h.get("end") or start)
                if start and start <= date_s <= end:
                    override = bool(h.get("occupied", False))
                    break

    if override is not None:
        return {"occupied": override, "reason": "holiday_override", "day": day_key}

    d = weekly.get(day_key) if isinstance(weekly, dict) else None
    if not isinstance(d, dict):
        d = _default_day_block()
    if not bool(d.get("occupied", False)):
        return {"occupied": False, "reason": "weekly_unoccupied", "day": day_key}
    start_m = int(d.get("startMinutes", 8 * 60))
    end_m = int(d.get("endMinutes", 17 * 60))
    if start_m <= mins <= end_m:
        return {"occupied": True, "reason": "weekly_window", "day": day_key}
    return {"occupied": False, "reason": "outside_window", "day": day_key}


def _schedule_item_to_bacnet_weekly(s: dict[str, Any]) -> list[list[dict[str, Any]]]:
    days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    weekly = s.get("weekly", {}) if isinstance(s, dict) else {}
    out: list[list[dict[str, Any]]] = []
    for d in days:
        row = weekly.get(d, {}) if isinstance(weekly, dict) else {}
        occ = bool(row.get("occupied", False)) if isinstance(row, dict) else False
        start_m = int(row.get("startMinutes", 8 * 60)) if isinstance(row, dict) else 8 * 60
        end_m = int(row.get("endMinutes", 17 * 60)) if isinstance(row, dict) else 17 * 60
        start_m = max(0, min(24 * 60, start_m))
        end_m = max(0, min(24 * 60, end_m))
        if not occ:
            out.append([])
            continue

        def _fmt(m: int) -> str:
            h = m // 60
            mm = m % 60
            return f"{h:02d}:{mm:02d}"

        if start_m < end_m:
            out.append([{"time": _fmt(start_m), "value": 1}, {"time": _fmt(end_m), "value": 0}])
        elif start_m == end_m:
            out.append([{"time": _fmt(start_m), "value": 1}])
        else:
            # Overnight split; keep this day occupied from start->midnight.
            out.append([{"time": _fmt(start_m), "value": 1}, {"time": "23:59:59", "value": 0}])
    return out


async def _push_hosted_schedule_to_bacnet(doc: dict[str, Any]) -> dict[str, Any]:
    schedules = doc.get("schedules", [])
    if not isinstance(schedules, list) or not schedules:
        return {"ok": False, "message": "no schedules available"}
    selected = schedules[0] if isinstance(schedules[0], dict) else {}
    schedule_name = str(doc.get("hostedScheduleName") or "occupancy-schedule")
    payload = {
        "jsonrpc": "2.0",
        "id": "bas-lite-schedule-sync",
        "method": "server_update_schedule",
        "params": {
            "update": {
                "name": schedule_name,
                "schedule_default": 0,
                "weekly_schedule": _schedule_item_to_bacnet_weekly(selected),
            }
        },
    }
    base = os.environ.get("SUPERVISOR_BACNET_RPC_URL", "http://diy-bacnet:8080").rstrip("/")
    entry = os.environ.get("SUPERVISOR_BACNET_RPC_ENTRYPOINT", "/api").strip()
    if not entry.startswith("/"):
        entry = "/" + entry
    url = f"{base}{entry}"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    tok = (os.environ.get("BACNET_RPC_API_KEY") or "").strip()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    async with httpx.AsyncClient(timeout=8.0) as c:
        r = await c.post(url, headers=headers, json=payload)
        if r.status_code >= 400:
            return {"ok": False, "message": f"rpc http {r.status_code}", "body": r.text[:300]}
        body = r.json() if r.text else {}
        if isinstance(body, dict) and body.get("error"):
            return {"ok": False, "message": str(body.get("error"))}
        return {"ok": True, "url": url, "scheduleName": schedule_name}


def _load_alarm_rules() -> list[dict[str, Any]]:
    body = _read_json_file(ALARM_RULES_PATH, {"items": []})
    items = body.get("items") if isinstance(body, dict) else []
    return items if isinstance(items, list) else []


def _load_alarm_state() -> dict[str, Any]:
    d = _read_json_file(ALARM_STATE_PATH, {"rules": {}, "history": []})
    if not isinstance(d, dict):
        return {"rules": {}, "history": []}
    d.setdefault("rules", {})
    d.setdefault("history", [])
    return d


def _save_alarm_state(state: dict[str, Any]) -> None:
    hist = state.get("history", [])
    if isinstance(hist, list):
        state["history"] = hist[-500:]
    _write_json_file(ALARM_STATE_PATH, state)


def _notification_cfg() -> dict[str, Any]:
    cfg = _read_json_file(
        NOTIFICATIONS_CFG_PATH,
        {
            "smtp": {
                "enabled": False,
                "host": "",
                "port": 587,
                "username": "",
                "password": "",
                "from": "",
                "to": [],
                "starttls": True,
                "ssl": False,
                "timeoutSec": 8,
            }
        },
    )
    return cfg if isinstance(cfg, dict) else {"smtp": {"enabled": False}}


def _send_email_if_configured(subject: str, body: str) -> dict[str, Any]:
    cfg = _notification_cfg().get("smtp", {})
    if not isinstance(cfg, dict) or not cfg.get("enabled"):
        return {"ok": False, "message": "smtp disabled"}
    host = str(cfg.get("host", "")).strip()
    sender = str(cfg.get("from", "")).strip()
    recipients = cfg.get("to", [])
    if not host or not sender or not isinstance(recipients, list) or not recipients:
        return {"ok": False, "message": "smtp config incomplete"}
    port = int(cfg.get("port", 587) or 587)
    timeout = int(cfg.get("timeoutSec", 8) or 8)
    use_ssl = bool(cfg.get("ssl", False))
    use_starttls = bool(cfg.get("starttls", True))
    username = str(cfg.get("username", "")).strip()
    password = str(cfg.get("password", "")).strip()
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(str(x) for x in recipients)
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port, timeout=timeout, context=ssl.create_default_context()) as server:
                if username:
                    server.login(username, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=timeout) as server:
                if use_starttls:
                    server.starttls(context=ssl.create_default_context())
                if username:
                    server.login(username, password)
                server.send_message(msg)
        return {"ok": True, "message": "sent"}
    except Exception as exc:
        logger.exception("smtp send failed")
        return {"ok": False, "message": str(exc)}


def _evaluate_alarm_rules(ts: str, point_values: dict[str, Any], point_meta: dict[str, dict[str, Any]]) -> None:
    rules = _load_alarm_rules()
    state = _load_alarm_state()
    states = state.setdefault("rules", {})
    history = state.setdefault("history", [])
    changed = False

    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict):
            continue
        rule_id = str(rule.get("id") or f"rule_{idx+1}")
        rule_type = str(rule.get("type") or "out_of_range")
        if not bool(rule.get("enabled", True)):
            continue
        point_id = str(rule.get("pointId") or "").strip()
        if not point_id:
            continue
        cur = states.get(rule_id) if isinstance(states.get(rule_id), dict) else {}
        cur.setdefault("status", "normal")
        cur.setdefault("pendingSince", None)
        cur.setdefault("activeSince", None)
        cur.setdefault("clearPendingSince", None)
        cur.setdefault("acknowledged", False)

        active_condition = False
        reading = point_values.get(point_id)
        if rule_type == "status_mismatch":
            cmd_id = str(rule.get("commandPointId") or "").strip()
            cmd_val = point_values.get(cmd_id)
            expected_on = rule.get("expectedOnValue", 1)
            expected_off = rule.get("expectedOffValue", 0)
            expected = expected_on if _is_truthy(cmd_val) else expected_off
            active_condition = reading != expected
        else:
            val = _to_float(reading)
            lo = _to_float(rule.get("low"))
            hi = _to_float(rule.get("high"))
            if val is not None:
                if lo is not None and val < lo:
                    active_condition = True
                if hi is not None and val > hi:
                    active_condition = True

        assert_delay = int(rule.get("assertDelaySec") or rule.get("mismatchDelaySec") or 0)
        clear_delay = int(rule.get("clearDelaySec") or 0)

        def _elapsed(start_iso: Optional[str]) -> float:
            if not start_iso:
                return 0.0
            try:
                start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
                now = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return (now - start).total_seconds()
            except Exception:
                return 0.0

        if active_condition:
            cur["clearPendingSince"] = None
            if cur["status"] == "active":
                pass
            else:
                if not cur.get("pendingSince"):
                    cur["pendingSince"] = ts
                    cur["status"] = "pending"
                    changed = True
                if _elapsed(cur.get("pendingSince")) >= max(0, assert_delay):
                    cur["status"] = "active"
                    cur["activeSince"] = ts
                    cur["pendingSince"] = None
                    cur["acknowledged"] = False
                    msg = str(rule.get("message") or f"Alarm {rule_id} active")
                    severity = str(rule.get("severity") or "warning")
                    hist = {
                        "id": str(uuid4()),
                        "ruleId": rule_id,
                        "severity": severity,
                        "state": "active",
                        "message": msg,
                        "triggeredAt": ts,
                        "deviceId": point_meta.get(point_id, {}).get("deviceId"),
                        "pointId": point_id,
                        "acknowledged": False,
                    }
                    history.append(hist)
                    notify = _send_email_if_configured(
                        subject=f"[BAS Lite][{severity.upper()}] {msg}",
                        body=f"{msg}\nruleId={rule_id}\npointId={point_id}\nvalue={reading}\nts={ts}",
                    )
                    _append_notification_log({"ts": ts, "kind": "alarm_active", "ruleId": rule_id, "result": notify})
                    changed = True
        else:
            cur["pendingSince"] = None
            if cur["status"] in ("active", "clear_pending"):
                if not cur.get("clearPendingSince"):
                    cur["clearPendingSince"] = ts
                    cur["status"] = "clear_pending"
                    changed = True
                if _elapsed(cur.get("clearPendingSince")) >= max(0, clear_delay):
                    cur["status"] = "normal"
                    cur["activeSince"] = None
                    cur["clearPendingSince"] = None
                    changed = True
            else:
                cur["status"] = "normal"
            # close active history rows for this rule
            for ev in reversed(history):
                if ev.get("ruleId") == rule_id and ev.get("state") == "active" and not ev.get("clearedAt"):
                    ev["clearedAt"] = ts
                    ev["state"] = "cleared"
                    changed = True
                    break

        states[rule_id] = cur

    if changed:
        _save_alarm_state(state)


async def _snapshot_trends(app: Any) -> None:
    """Background: sample all point last_value into ring buffers."""
    await asyncio.sleep(3)
    while True:
        try:
            coord: SupervisorCoordinator = app.state.coordinator
            devices = await coord.list_devices(enabled_only=False)
            buf: Dict[str, Deque[dict[str, Any]]] = app.state.trend_buffers
            ts = _utc()
            point_values: dict[str, Any] = {}
            point_meta: dict[str, dict[str, Any]] = {}
            for d in devices:
                pts = await coord.list_points(d.id, enabled_only=False)
                for p in pts:
                    val = p.decoded_value()
                    entry = {"t": ts, "value": val}
                    buf[p.id].append(entry)
                    point_values[p.id] = val
                    point_meta[p.id] = {"deviceId": d.id, "label": p.name or p.object_identifier}
            _evaluate_alarm_rules(ts=ts, point_values=point_values, point_meta=point_meta)
            _publish_event(
                app,
                "points.updated",
                {
                    "deviceCount": len(devices),
                    "pointCount": len(point_values),
                    "sampleTs": ts,
                },
            )
            _publish_event(app, "alarms.updated", {"sampleTs": ts})
            _publish_event(app, "schedule.updated", {"sampleTs": ts})
            _publish_event(app, "system.metrics.updated", {"sampleTs": ts})
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("trend snapshot failed")
        await asyncio.sleep(TREND_INTERVAL_SEC)


def register_legacy(app: Any) -> None:
    app.include_router(router, prefix="/app8/api", tags=["bas-lite-legacy"])

    @app.on_event("startup")
    async def _start_trend_worker() -> None:
        app.state.trend_buffers = defaultdict(lambda: deque(maxlen=TREND_MAX))
        app.state._trend_task = asyncio.create_task(_snapshot_trends(app))
        DRIVER_CFG_DIR.mkdir(parents=True, exist_ok=True)
        DISCOVERY_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)
        ALARM_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        NOTIFICATIONS_CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not NOTIFICATIONS_CFG_PATH.is_file():
            _write_json_file(
                NOTIFICATIONS_CFG_PATH,
                {
                    "smtp": {
                        "enabled": False,
                        "host": "",
                        "port": 587,
                        "username": "",
                        "password": "",
                        "from": "",
                        "to": [],
                        "starttls": True,
                        "ssl": False,
                        "timeoutSec": 8,
                    }
                },
            )
        logger.info("bas-lite legacy routes mounted; trend worker started")

    @app.on_event("shutdown")
    async def _stop_trend_worker() -> None:
        t = getattr(app.state, "_trend_task", None)
        if t:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass


@router.get("/health")
async def health(request: Request) -> dict:
    coord = _coord(request)
    devices = await coord.list_devices(enabled_only=False)
    n_dev = len(devices)
    n_pts = 0
    for d in devices:
        n_pts += len(await coord.list_points(d.id, enabled_only=False))
    return {
        "status": "ok",
        "appTitle": "BAS Lite",
        "siteName": os.environ.get("BAS_LITE_SITE_NAME", "Edge site (Docker + easy-aso)"),
        "routePrefix": "/app8",
        "agentIdentity": "easy-aso-supervisor",
        "lastPublishAt": None,
        "defaultTrendPointId": None,
        "counts": {"devices": n_dev, "points": n_pts, "activeAlarms": 0},
        "trendPolicy": {
            "intervalMinutes": max(1, int(TREND_INTERVAL_SEC // 60) or 1),
            "retentionDays": 7,
            "maxSamplesPerPoint": TREND_MAX,
        },
        "runtimeModel": {
            "status": "docker_easy_aso",
            "subscriptions": [],
            "note": "Stack is Docker + easy-aso supervisor.",
        },
    }


@router.get("/devices")
async def devices(request: Request) -> dict:
    coord = _coord(request)
    rt = request.app.state.runtime
    items = []
    for d in await coord.list_devices(enabled_only=False):
        h = rt.device_health(d.id)
        status = h.status if h else "unknown"
        pts = await coord.list_points(d.id, enabled_only=False)
        items.append(
            {
                "id": d.id,
                "name": d.name,
                "displayName": d.name.replace("_", " ").title(),
                "kind": _device_kind(d.name),
                "address": d.device_address,
                "deviceId": _parse_device_id_numeric(d.device_address),
                "status": status,
                "lastSeen": h.last_poll_at if h else None,
                "pollingEnabled": d.enabled,
                "pointCount": len(pts),
            }
        )
    return {"items": items}


@router.get("/points")
async def points(
    request: Request,
    deviceId: Optional[str] = Query(None, alias="deviceId"),
) -> dict:
    coord = _coord(request)
    rows: List[dict] = []
    for d in await coord.list_devices(enabled_only=False):
        if deviceId and d.id != deviceId:
            continue
        for p in await coord.list_points(d.id, enabled_only=False):
            rows.append(
                {
                    "id": p.id,
                    "deviceId": d.id,
                    "name": p.name or p.object_identifier,
                    "label": p.name or p.object_identifier,
                    "units": "",
                    "kind": "analog" if isinstance(p.decoded_value(), (int, float)) else "binary",
                    "value": p.decoded_value(),
                    "lastUpdated": p.last_polled_at,
                    "alarmState": "normal",
                    "trendEnabled": True,
                    "adjustable": p.property_identifier.lower() in ("present-value", "present_value"),
                    "graphicGroup": "default",
                }
            )
    return {"items": rows}


class SetpointWrite(BaseModel):
    pointId: str
    value: Any


@router.post("/setpoints/write")
async def setpoints_write(request: Request, body: SetpointWrite) -> dict:
    coord = _coord(request)
    p = await coord.get_point(body.pointId)
    if p is None:
        return {"status": "error", "message": f"Unknown pointId: {body.pointId}"}
    d = await coord.get_device(p.device_id)
    if d is None:
        return {"status": "error", "message": "device not found"}
    if d.driver_type != "bacnet_jsonrpc":
        return {
            "status": "error",
            "message": f"Writes only supported for bacnet_jsonrpc driver (got {d.driver_type})",
        }
    client = JsonRpcBacnetClient(
        d.rpc_base_url or os.environ.get("SUPERVISOR_BACNET_RPC_URL", "http://127.0.0.1:8080"),
        entrypoint=d.rpc_entrypoint or os.environ.get("SUPERVISOR_BACNET_RPC_ENTRYPOINT", "/api"),
    )
    try:
        val: Any = body.value
        if isinstance(val, str) and val.replace(".", "", 1).isdigit():
            val = float(val) if "." in val else int(val)
        await client.write(d.device_address, p.object_identifier, val, property_identifier=p.property_identifier)
        now = _utc()
        return {
            "status": "ok",
            "pointId": p.id,
            "deviceId": d.id,
            "pointName": p.name,
            "requestedValue": val,
            "result": "written",
            "timestamp": now,
        }
    except Exception as exc:
        logger.exception("setpoint write")
        return {"status": "error", "pointId": body.pointId, "message": str(exc)}
    finally:
        await client.close()


@router.get("/trends")
async def trends(request: Request, pointId: Optional[str] = Query(None)) -> dict:
    coord = _coord(request)
    pts: List[Any] = []
    for d in await coord.list_devices(enabled_only=False):
        pts.extend(await coord.list_points(d.id, enabled_only=False))
    if not pts:
        return {"pointId": "", "label": "", "units": None, "items": [], "summary": {}}
    pid = pointId or pts[0].id
    meta = next((p for p in pts if p.id == pid), pts[0])
    buf = _trend_buf(request)
    series = list(buf.get(meta.id, []))
    values = [s["value"] for s in series if isinstance(s.get("value"), (int, float))]
    latest = values[-1] if values else meta.decoded_value()
    return {
        "pointId": meta.id,
        "label": meta.name or meta.object_identifier,
        "units": "",
        "retentionDays": 7,
        "intervalMinutes": max(1, int(TREND_INTERVAL_SEC // 60) or 1),
        "items": series,
        "summary": {
            "latest": latest,
            "min": min(values) if values else None,
            "max": max(values) if values else None,
            "avg": round(sum(values) / len(values), 2) if values else None,
        },
    }


@router.get("/alarms/events")
async def alarm_events(request: Request) -> dict:
    state = _load_alarm_state()
    items = state.get("history", []) if isinstance(state.get("history"), list) else []
    # newest first, include active and recent cleared/acked events
    items = list(reversed(items[-300:]))
    return {"items": items}


@router.get("/alarms/definitions")
async def alarm_definitions() -> dict:
    if ALARM_RULES_PATH.is_file():
        try:
            body = json.loads(ALARM_RULES_PATH.read_text(encoding="utf-8"))
            if isinstance(body, dict) and isinstance(body.get("items"), list):
                return {"items": body["items"]}
        except Exception:
            logger.exception("alarm rules parse failed")
    return {"items": []}


class AlarmDefinitionStore(BaseModel):
    items: List[dict]


@router.post("/alarms/definitions")
async def alarm_definitions_store(body: AlarmDefinitionStore) -> dict:
    ALARM_RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    ALARM_RULES_PATH.write_text(json.dumps({"items": body.items}, indent=2), encoding="utf-8")
    return {"status": "ok", "count": len(body.items), "path": str(ALARM_RULES_PATH)}


class AlarmAckBody(BaseModel):
    eventId: str
    note: Optional[str] = None


@router.post("/alarms/ack")
async def alarms_ack(body: AlarmAckBody) -> dict:
    state = _load_alarm_state()
    ts = _utc()
    found = False
    history = state.get("history", [])
    if isinstance(history, list):
        for ev in history:
            if isinstance(ev, dict) and ev.get("id") == body.eventId:
                ev["acknowledged"] = True
                ev["acknowledgedAt"] = ts
                if body.note:
                    ev["ackNote"] = body.note
                found = True
                rule_id = ev.get("ruleId")
                if isinstance(rule_id, str):
                    r = state.get("rules", {}).get(rule_id)
                    if isinstance(r, dict):
                        r["acknowledged"] = True
                break
    if found:
        _save_alarm_state(state)
    return {"status": "ok" if found else "error", "eventId": body.eventId, "acknowledgedAt": ts, "note": body.note or ""}


@router.get("/discovery/export")
async def discovery_export(request: Request) -> dict:
    coord = _coord(request)
    devices_payload: List[dict[str, Any]] = []
    for d in await coord.list_devices(enabled_only=False):
        points_payload = []
        for p in await coord.list_points(d.id, enabled_only=False):
            points_payload.append(
                {
                    "id": p.id,
                    "name": p.name,
                    "objectIdentifier": p.object_identifier,
                    "propertyIdentifier": p.property_identifier,
                    "value": p.decoded_value(),
                    "lastPolledAt": p.last_polled_at,
                }
            )
        devices_payload.append(
            {
                "id": d.id,
                "name": d.name,
                "protocol": "bacnet",
                "driverType": d.driver_type,
                "deviceAddress": d.device_address,
                "enabled": d.enabled,
                "points": points_payload,
            }
        )
    payload = {
        "schemaVersion": 1,
        "generatedAt": _utc(),
        "siteName": os.environ.get("BAS_LITE_SITE_NAME", "Boss Pi BAS Lite"),
        "devices": devices_payload,
        "notes": {
            "intendedUse": "AI-assisted point curation and alarm/trend config authoring",
            "modbusSupport": "Add protocol=modbus entries and import as driver configs in this same shape",
        },
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = DISCOVERY_EXPORT_DIR / f"discovery_{stamp}.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"status": "ok", "path": str(out_path), "payload": payload}


@router.post("/discovery/import")
async def discovery_import(body: dict = Body(...)) -> dict:
    DISCOVERY_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    in_path = DISCOVERY_EXPORT_DIR / f"import_{stamp}.json"
    in_path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    return {
        "status": "ok",
        "path": str(in_path),
        "message": "Import payload stored. Apply edits through Driver configs + alarm definitions workflows.",
    }


def _driver_configs_bundle() -> dict[str, str]:
    DRIVER_CFG_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[str, str] = {}
    for p in DRIVER_CFG_DIR.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(DRIVER_CFG_DIR).as_posix()
        out[rel] = p.read_text(encoding="utf-8")
    return out


@router.get("/backup/export")
async def backup_export() -> dict:
    payload = {
        "schemaVersion": 1,
        "exportedAt": _utc(),
        "siteName": os.environ.get("BAS_LITE_SITE_NAME", "Boss Pi BAS Lite"),
        "schedule": _read_json_file(SCHEDULE_PATH, {}),
        "alarmDefinitions": _read_json_file(ALARM_RULES_PATH, {"items": []}),
        "alarmState": _load_alarm_state(),
        "notifications": _notification_cfg(),
        "driverConfigs": _driver_configs_bundle(),
        "discoveryExports": {
            p.name: p.read_text(encoding="utf-8")
            for p in sorted(DISCOVERY_EXPORT_DIR.glob("*.json"))
            if p.is_file()
        },
    }
    return {"status": "ok", "payload": payload}


@router.post("/backup/restore")
async def backup_restore(body: dict = Body(...)) -> dict:
    payload = body.get("payload", body) if isinstance(body, dict) else {}
    if not isinstance(payload, dict):
        raise HTTPException(400, "payload must be object")
    if "schedule" in payload and isinstance(payload["schedule"], dict):
        _write_json_file(SCHEDULE_PATH, payload["schedule"])
    if "alarmDefinitions" in payload and isinstance(payload["alarmDefinitions"], dict):
        _write_json_file(ALARM_RULES_PATH, payload["alarmDefinitions"])
    if "alarmState" in payload and isinstance(payload["alarmState"], dict):
        _save_alarm_state(payload["alarmState"])
    if "notifications" in payload and isinstance(payload["notifications"], dict):
        _write_json_file(NOTIFICATIONS_CFG_PATH, payload["notifications"])
    if "driverConfigs" in payload and isinstance(payload["driverConfigs"], dict):
        for rel, text in payload["driverConfigs"].items():
            if not isinstance(rel, str) or not isinstance(text, str):
                continue
            if ".." in rel or rel.startswith("/"):
                continue
            fp = DRIVER_CFG_DIR / rel
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(text, encoding="utf-8")
    return {"status": "ok", "restoredAt": _utc()}


@router.get("/polling")
async def polling(request: Request) -> dict:
    out = await devices(request)
    return {
        "devices": [
            {
                "deviceId": x["id"],
                "name": x["displayName"],
                "pollingEnabled": x["pollingEnabled"],
                "lastSeen": x["lastSeen"],
            }
            for x in out["items"]
        ]
    }


@router.get("/schedule")
async def schedule_get() -> dict:
    if SCHEDULE_PATH.is_file():
        doc = _normalize_schedule_doc(_read_json_file(SCHEDULE_PATH, {}))
    else:
        doc = _normalize_schedule_doc({})
    return doc


@router.post("/schedule")
async def schedule_post(body: dict = Body(...)) -> dict:
    doc = _normalize_schedule_doc(body)
    SCHEDULE_PATH.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    sync_result = await _push_hosted_schedule_to_bacnet(doc)
    return {"status": "ok", "bacnetScheduleSync": sync_result}


@router.get("/schedule/effective")
async def schedule_effective(request: Request) -> dict:
    doc = await schedule_get()
    now = datetime.now()
    schedules = doc.get("schedules", [])
    if not isinstance(schedules, list):
        schedules = []

    by_schedule = []
    assigned: dict[str, dict[str, Any]] = {}
    for s in schedules:
        if not isinstance(s, dict):
            continue
        eff = _effective_for_schedule(s, now)
        sid = str(s.get("id") or "")
        by_schedule.append(
            {
                "id": sid,
                "label": s.get("label", sid),
                "occupied": bool(eff["occupied"]),
                "reason": eff["reason"],
                "day": eff["day"],
            }
        )
        for did in s.get("assignments", []) or []:
            assigned[str(did)] = {"scheduleId": sid, "scheduleLabel": s.get("label", sid), **eff}

    devices_payload = []
    for d in await _coord(request).list_devices(enabled_only=False):
        s = assigned.get(d.id)
        devices_payload.append(
            {
                "deviceId": d.id,
                "deviceName": d.name,
                "occupied": bool(s["occupied"]) if s else False,
                "reason": s["reason"] if s else "unassigned",
                "scheduleId": s["scheduleId"] if s else None,
                "scheduleLabel": s["scheduleLabel"] if s else None,
            }
        )

    return {
        "timestamp": _utc(),
        "localTime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "schedules": by_schedule,
        "devices": devices_payload,
    }


@router.get("/system/metrics")
async def system_metrics() -> dict:
    mem = {}
    load = {"load1": None, "load5": None, "load15": None}
    disk: dict[str, Any] = {}
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if ":" in line:
                    k, v = line.split(":", 1)
                    mem[k.strip()] = int(v.split()[0]) * 1024
        total = mem.get("MemTotal")
        avail = mem.get("MemAvailable") or mem.get("MemFree")
        used = (total - avail) if total and avail else None
        mem_out = {"memTotalBytes": total, "memAvailableBytes": avail, "memUsedBytes": used}
    except OSError:
        mem_out = {"memTotalBytes": None, "memAvailableBytes": None, "memUsedBytes": None}
    try:
        with open("/proc/loadavg", encoding="utf-8") as f:
            parts = f.read().split()
            load = {"load1": float(parts[0]), "load5": float(parts[1]), "load15": float(parts[2])}
    except OSError:
        pass
    try:
        u = shutil.disk_usage("/")
        disk = {
            "path": "/",
            "totalBytes": u.total,
            "usedBytes": u.used,
            "freeBytes": u.free,
            "usedPercent": round(100.0 * u.used / u.total, 2) if u.total else None,
        }
    except OSError:
        disk = {"path": "/", "totalBytes": None, "usedBytes": None, "freeBytes": None, "usedPercent": None}
    cpu = None
    try:
        import psutil  # type: ignore

        cpu = round(psutil.cpu_percent(interval=0.1), 2)
    except Exception:
        pass
    return {
        "timestamp": _utc(),
        "cpuPercent": cpu,
        "loadavg": load,
        "memory": mem_out,
        "diskRoot": disk,
        "hostname": os.environ.get("HOSTNAME"),
    }


@router.get("/system/time")
async def system_time() -> dict:
    now = datetime.now()
    return {
        "timestamp": _utc(),
        "localDate": now.strftime("%Y-%m-%d"),
        "localTime": now.strftime("%H:%M:%S"),
        "weekday": now.strftime("%A"),
    }


@router.get("/system/messaging")
async def system_messaging() -> dict:
    rpc_base = os.environ.get("SUPERVISOR_BACNET_RPC_URL", "http://diy-bacnet:8080")
    rpc_ok = False
    err = ""
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(rpc_base.rstrip("/") + "/")
            rpc_ok = r.status_code < 500
    except Exception as exc:
        err = str(exc)
    return {
        "bacnetOnline": rpc_ok,
        "bacnetRpcUrl": rpc_base,
        "mqttBridgeOnline": False,
        "mqttBrokerUrl": os.environ.get("BAS_LITE_MQTT_BROKER_URL", ""),
        "note": "MQTT bridge is planned. BACnet uses diy-bacnet JSON-RPC today.",
        "error": err,
    }


def _docker_client():
    if docker is None:
        return None
    try:
        return docker.from_env()
    except Exception:
        return None


@router.get("/system/containers")
async def system_containers() -> dict:
    client = _docker_client()
    if client is None:
        return {"dockerAvailable": False, "items": [], "message": "Docker socket/client unavailable in api container."}
    try:
        items = []
        # Focus this compose project first.
        containers = client.containers.list(all=True, filters={"label": [f"com.docker.compose.project={COMPOSE_PROJECT_NAME}"]})
        for c in containers:
            env_list = (c.attrs or {}).get("Config", {}).get("Env") or []
            env_map: dict[str, str] = {}
            for entry in env_list:
                if "=" in entry:
                    k, _, v = entry.partition("=")
                    env_map[k] = v
            lbl = c.labels or {}
            items.append(
                {
                    "id": c.short_id,
                    "name": c.name,
                    "status": c.status,
                    "image": c.image.tags[0] if c.image.tags else "unknown",
                    "service": lbl.get("com.docker.compose.service", ""),
                    "easyAsoAgentModule": env_map.get("EASY_ASO_AGENT_MODULE", ""),
                    "easyAsoAgentClass": env_map.get("EASY_ASO_AGENT_CLASS", ""),
                    "easyAsoRole": lbl.get("bas-lite.easy-aso.role", ""),
                }
            )
        items.sort(key=lambda x: x["name"])
        return {"dockerAvailable": True, "items": items}
    except Exception as exc:
        return {"dockerAvailable": False, "items": [], "message": str(exc)}


@router.get("/system/container-logs")
async def system_container_logs(name: str = Query(...), tail: int = Query(120, ge=20, le=500)) -> dict:
    client = _docker_client()
    if client is None:
        return {"dockerAvailable": False, "name": name, "logs": "", "message": "Docker socket/client unavailable."}
    try:
        c = client.containers.get(name)
        raw = c.logs(tail=tail).decode("utf-8", errors="replace")
        return {"dockerAvailable": True, "name": name, "logs": raw}
    except Exception as exc:
        return {"dockerAvailable": False, "name": name, "logs": "", "message": str(exc)}


@router.get("/system/container-logs/stream")
async def system_container_logs_stream(name: str = Query(...), backlog: int = Query(80, ge=0, le=500)):
    client = _docker_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Docker socket/client unavailable.")

    async def event_gen():
        # Send initial backlog first so operator has immediate context.
        try:
            c = client.containers.get(name)
            raw = c.logs(tail=backlog).decode("utf-8", errors="replace") if backlog > 0 else ""
            if raw:
                for ln in raw.splitlines():
                    yield f"data: {ln}\n\n"
            else:
                yield "data: [connected]\n\n"
        except Exception as exc:
            yield f"event: error\ndata: {str(exc)}\n\n"
            return

        # Poll Docker logs and stream incremental lines.
        # `since` is seconds precision; we use a 1s overlap and de-dup cache.
        since = int(datetime.now().timestamp()) - 1
        seen: Deque[str] = deque(maxlen=600)
        while True:
            try:
                c = client.containers.get(name)
                chunk = c.logs(since=since, tail=0).decode("utf-8", errors="replace")
                since = int(datetime.now().timestamp()) - 1
                if chunk:
                    for ln in chunk.splitlines():
                        if ln in seen:
                            continue
                        seen.append(ln)
                        yield f"data: {ln}\n\n"
                else:
                    yield "event: keepalive\ndata: tick\n\n"
            except Exception as exc:
                yield f"event: error\ndata: {str(exc)}\n\n"
                return
            await asyncio.sleep(1.0)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


class ContainerActionBody(BaseModel):
    name: str
    action: str


def _compose_guarded_container(client: Any, name: str) -> Any:
    c = client.containers.get(name)
    labels = c.labels or {}
    if labels.get("com.docker.compose.project") != COMPOSE_PROJECT_NAME:
        raise HTTPException(status_code=403, detail="container is not part of this compose project")
    return c


@router.post("/system/container-action")
async def system_container_action(body: ContainerActionBody) -> dict:
    """restart | stop | start for compose-labeled containers (BAS Lite stack + optional agents)."""
    client = _docker_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Docker socket/client unavailable.")
    action = (body.action or "").strip().lower()
    if action not in ("restart", "stop", "start"):
        raise HTTPException(status_code=400, detail="action must be restart, stop, or start")
    try:
        c = _compose_guarded_container(client, body.name)
        if action == "restart":
            c.restart(timeout=60)
        elif action == "stop":
            c.stop(timeout=45)
        else:
            c.start()
        c.reload()
        return {"ok": True, "action": action, "name": body.name, "status": c.status}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("container action")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/agents/vctl")
async def agents_vctl() -> dict:
    return {
        "exitCode": 0,
        "stderr": "",
        "stdout": "Docker + easy-aso runtime.\n",
        "agents": [],
        "note": "Use `docker compose ps` and `docker compose logs` instead.",
    }


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
    await websocket.accept()
    app = websocket.app
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _event_subscribers(app).append(q)
    try:
        while True:
            try:
                evt = await asyncio.wait_for(q.get(), timeout=5.0)
            except asyncio.TimeoutError:
                evt = {"type": "event", "topic": "system.tick", "ts": _utc(), "payload": {}}
            await websocket.send_json(evt)
    except WebSocketDisconnect:
        return
    finally:
        subs = _event_subscribers(app)
        if q in subs:
            subs.remove(q)


@router.post("/agents/lifecycle")
async def agents_lifecycle() -> dict:
    return {"status": "error", "message": "Agent lifecycle is not available in the Docker stack."}


@router.get("/driver/configs")
async def driver_configs_list() -> dict:
    DRIVER_CFG_DIR.mkdir(parents=True, exist_ok=True)
    keys: set[str] = set()
    for p in DRIVER_CFG_DIR.rglob("*.json"):
        rel = p.relative_to(DRIVER_CFG_DIR).with_suffix("")
        keys.add(str(rel).replace("\\", "/"))
    for p in DRIVER_CFG_DIR.rglob("*.csv"):
        rel = p.relative_to(DRIVER_CFG_DIR).with_suffix("")
        keys.add(str(rel).replace("\\", "/"))
    return {"exitCode": 0, "stderr": "", "items": sorted(keys)}


def _driver_cfg_path(name: str, *, csv: bool = False) -> Path:
    if ".." in name or name.startswith("/"):
        raise HTTPException(400, "invalid name")
    p = (DRIVER_CFG_DIR / name).with_suffix(".csv" if csv else ".json")
    return p


@router.get("/driver/config")
async def driver_config_get(name: str = Query(...)) -> dict:
    for csv in (False, True):
        path = _driver_cfg_path(name, csv=csv)
        if path.is_file():
            return {"name": name, "exitCode": 0, "stderr": "", "content": path.read_text(encoding="utf-8")}
    raise HTTPException(404, "config not found")


class DriverStore(BaseModel):
    name: str
    content: Any
    csv: bool = False


@router.post("/driver/config/store")
async def driver_config_store(body: DriverStore) -> dict:
    DRIVER_CFG_DIR.mkdir(parents=True, exist_ok=True)
    path = _driver_cfg_path(body.name, csv=body.csv)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = (
        body.content
        if isinstance(body.content, str)
        else json.dumps(body.content, indent=2)
    )
    path.write_text(text, encoding="utf-8")
    return {"status": "ok", "exitCode": 0, "stdout": f"wrote {path}", "stderr": ""}


class DriverDelete(BaseModel):
    name: str


@router.post("/driver/config/delete")
async def driver_config_delete(body: DriverDelete) -> dict:
    for csv in (False, True):
        path = _driver_cfg_path(body.name, csv=csv)
        if path.is_file():
            path.unlink()
            return {"status": "ok", "exitCode": 0, "stdout": "deleted", "stderr": ""}
    return {"status": "error", "exitCode": 1, "message": "not found"}


@router.get("/notifications/logs")
async def notification_logs() -> dict:
    if not NOTIFICATIONS_LOG_PATH.is_file():
        return {"items": []}
    items: list[dict[str, Any]] = []
    with NOTIFICATIONS_LOG_PATH.open("r", encoding="utf-8") as f:
        for line in f.readlines()[-300:]:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                continue
    return {"items": items}


@router.get("/notifications/config")
async def notifications_config() -> dict:
    cfg = _notification_cfg()
    return {"smtp": cfg.get("smtp", {}), "emailNotificationSupported": True}


@router.post("/notifications/config")
async def notifications_config_store(body: dict = Body(...)) -> dict:
    smtp_cfg = body.get("smtp", {}) if isinstance(body, dict) else {}
    if not isinstance(smtp_cfg, dict):
        raise HTTPException(400, "smtp must be object")
    _write_json_file(NOTIFICATIONS_CFG_PATH, {"smtp": smtp_cfg})
    return {"status": "ok", "path": str(NOTIFICATIONS_CFG_PATH)}


@router.post("/notifications/test-email")
async def notifications_test_email(body: dict = Body(default={})) -> dict:
    subject = str(body.get("subject") or "BAS Lite test email")
    text = str(body.get("text") or f"SMTP test from BAS Lite at {_utc()}")
    res = _send_email_if_configured(subject=subject, body=text)
    _append_notification_log({"ts": _utc(), "kind": "smtp_test", "result": res})
    return res


@router.get("/setpoints")
async def setpoints(request: Request, deviceId: Optional[str] = Query(None)) -> dict:
    data = await points(request, deviceId=deviceId)
    items = [i for i in data["items"] if i.get("adjustable")]
    return {"items": items}


@router.get("/graphics/overview")
async def graphics_overview(request: Request) -> dict:
    devs = await devices(request)
    pts = await points(request)
    return {
        "systemOverview": {
            "siteName": os.environ.get("BAS_LITE_SITE_NAME", "Edge site"),
            "equipment": devs["items"],
        },
        "equipmentGraphics": {
            "default": {
                "groupKey": "default",
                "deviceIds": sorted({p["deviceId"] for p in pts["items"]}),
                "points": pts["items"],
            }
        },
    }
