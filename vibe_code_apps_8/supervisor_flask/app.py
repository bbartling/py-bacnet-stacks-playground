"""
Learning supervisor: Flask + JSON files + WebSockets + diy-bacnet JSON-RPC.

Serves the vanilla UI from ../vannila and implements /api/* for the dashboard.
Persists schedule editor state to schedules.json and pushes the active profile to
diy-bacnet-server via server_update_schedule (see docs/server-rpc.md).
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import requests
from flask import Flask, abort, jsonify, request, send_from_directory
from flask_sock import Sock

import json_store
import rpc_client
from schedules_bridge import active_profile_payload

APP_DIR = Path(__file__).resolve().parent
WEBROOT = Path(os.environ.get("SUPERVISOR_WEBROOT", str(APP_DIR.parent / "vannila"))).resolve()

app = Flask(__name__)
sock = Sock(app)

_clients_lock = threading.Lock()
_ws_clients: list = []

# Optional background poll of diy-bacnet present values → WebSocket fan-out
_poll_stop = threading.Event()
_poll_thread: threading.Thread | None = None


def _broadcast(obj: dict) -> None:
    raw = json.dumps(obj)
    with _clients_lock:
        snapshot = list(_ws_clients)
    for ws in snapshot:
        try:
            ws.send(raw)
        except Exception:
            with _clients_lock:
                if ws in _ws_clients:
                    _ws_clients.remove(ws)


def _diy_base() -> str:
    settings = json_store.read_json("app_settings.json", {})
    return str(settings.get("diyBacnetUrl") or os.environ.get("DIY_BACNET_URL", "http://127.0.0.1:5000")).rstrip(
        "/"
    )


def _schedule_object_name() -> str:
    settings = json_store.read_json("app_settings.json", {})
    return str(
        settings.get("diyScheduleObjectName")
        or os.environ.get("DIY_SCHEDULE_OBJECT_NAME", "WeeklyOccupancy")
    )


def _diy_ping() -> tuple[bool, str]:
    try:
        rpc_client.server_hello(base_url=_diy_base())
        return True, "reachable"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _start_poll_thread() -> None:
    global _poll_thread
    if os.environ.get("ENABLE_WS_POLL", "").lower() not in ("1", "true", "yes"):
        return
    if _poll_thread and _poll_thread.is_alive():
        return

    def loop() -> None:
        while not _poll_stop.is_set():
            try:
                res = rpc_client.server_read_all_values(base_url=_diy_base())
                inner = res.get("result", res)
                if isinstance(inner, dict):
                    doc = json_store.read_json("latest_values.json", {"values": {}})
                    doc["values"] = inner
                    doc["updatedAt"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    json_store.write_json("latest_values.json", doc)
                    _broadcast({"type": "values", "values": inner, "updatedAt": doc["updatedAt"]})
            except Exception as exc:  # noqa: BLE001
                _broadcast({"type": "diy_error", "message": str(exc)})
            _poll_stop.wait(float(os.environ.get("WS_POLL_INTERVAL", "8")))

    _poll_thread = threading.Thread(target=loop, daemon=True)
    _poll_thread.start()


@app.before_request
def _ensure_data_dir() -> None:
    if not getattr(app, "_supervisor_seeded", False):
        json_store.ensure_seed_files()
        app._supervisor_seeded = True  # type: ignore[attr-defined]
        _start_poll_thread()


@app.get("/")
def index() -> object:
    return send_from_directory(WEBROOT, "index.html")


@app.get("/<path:filename>")
def static_vannila(filename: str) -> object:
    if ".." in filename or filename.startswith("/"):
        abort(404)
    target = WEBROOT / filename
    try:
        target.resolve().relative_to(WEBROOT)
    except ValueError:
        abort(404)
    if not target.is_file():
        abort(404)
    return send_from_directory(WEBROOT, filename)


@app.get("/api/health")
def api_health() -> object:
    settings = json_store.read_json("app_settings.json", {})
    ok, msg = _diy_ping()
    alarms = json_store.read_json("alarm_history.json", {"items": []})
    active = sum(1 for a in alarms.get("items", []) if str(a.get("state", "")).lower() == "active")
    return jsonify(
        {
            "appTitle": settings.get("appTitle", "BAS Lite supervisor"),
            "siteName": settings.get("siteName", "Edge"),
            "routePrefix": settings.get("routePrefix", "/api"),
            "volttron": {"status": "diy-bacnet " + ("OK" if ok else "offline"), "detail": msg},
            "counts": {"activeAlarms": active},
            "diy": {"reachable": ok, "baseUrl": _diy_base(), "scheduleObject": _schedule_object_name()},
        }
    )


@app.get("/api/devices")
def api_devices() -> object:
    return jsonify(json_store.read_json("discovered_devices.json", {"items": []}))


@app.get("/api/points")
def api_points() -> object:
    base = json_store.read_json("discovered_points.json", {"items": []})
    latest = json_store.read_json("latest_values.json", {}).get("values") or {}
    items = []
    for row in base.get("items", []):
        key = f"{row.get('deviceId')}::{row.get('label')}"
        merged = dict(row)
        if key in latest:
            merged["value"] = latest[key]
        items.append(merged)
    return jsonify({"items": items})


@app.get("/api/alarms/events")
def api_alarms() -> object:
    data = json_store.read_json("alarm_history.json", {"items": []})
    active = [a for a in data.get("items", []) if str(a.get("state", "")).lower() == "active"]
    return jsonify({"items": active})


@app.get("/api/trends")
def api_trends() -> object:
    point_id = request.args.get("pointId", "demo")
    lv = json_store.read_json("latest_values.json", {}).get("values") or {}
    v = lv.get(point_id)
    now = time.strftime("%H:%M")
    items = [{"ts": now, "value": v}] if v is not None else []
    return jsonify({"pointId": point_id, "items": items})


@app.get("/api/notifications/logs")
def api_notifications() -> object:
    return jsonify(json_store.read_json("notifications.json", {"items": []}))


@app.get("/api/schedules")
def api_schedules_get() -> object:
    doc = json_store.read_json("schedules.json", {})
    return jsonify(doc)


@app.post("/api/schedules")
def api_schedules_post() -> object:
    body = request.get_json(force=True, silent=True)
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "expected JSON object"}), 400
    if not isinstance(body.get("schedules"), list) or not body["schedules"]:
        return jsonify({"ok": False, "error": "schedules[] required"}), 400

    json_store.write_json("schedules.json", body)

    diy_result: dict | None = None
    diy_err: str | None = None
    try:
        update = active_profile_payload(body, object_name=_schedule_object_name())
        diy_result = rpc_client.server_update_schedule(update, base_url=_diy_base())
    except (requests.RequestException, RuntimeError, OSError, ValueError) as exc:
        diy_err = str(exc)

    notes = json_store.read_json("notifications.json", {"items": []})
    entry = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "channel": "supervisor",
        "detail": "Schedule saved"
        + ("; BACnet push OK" if diy_err is None else f"; BACnet push failed: {diy_err}"),
    }
    notes.setdefault("items", []).insert(0, entry)
    json_store.write_json("notifications.json", notes)

    _broadcast(
        {
            "type": "schedule_updated",
            "payload": body,
            "diyError": diy_err,
            "diyResult": diy_result,
        }
    )

    return jsonify({"ok": True, "diyError": diy_err, "diyResult": diy_result})


@app.get("/api/diy/schedule")
def api_diy_read_schedule() -> object:
    """Debug: read hosted BACnet schedule object from diy-bacnet-server."""
    try:
        out = rpc_client.server_read_schedule(_schedule_object_name(), base_url=_diy_base())
        return jsonify(out)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 502


@sock.route("/ws")
def websocket_supervisor(ws) -> None:
    with _clients_lock:
        _ws_clients.append(ws)
    try:
        ws.send(json.dumps({"type": "hello", "message": "supervisor WebSocket (learning)"}))
        while True:
            msg = ws.receive(timeout=120)
            if msg is None:
                continue
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                continue
            if data.get("type") == "ping":
                ws.send(json.dumps({"type": "pong", "t": time.time()}))
    finally:
        with _clients_lock:
            if ws in _ws_clients:
                _ws_clients.remove(ws)


def create_app() -> Flask:
    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5050"))
    app.run(host=os.environ.get("BIND", "127.0.0.1"), port=port, debug=True, threaded=True)
