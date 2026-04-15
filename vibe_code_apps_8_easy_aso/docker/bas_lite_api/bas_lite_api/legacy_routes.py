"""Legacy /app8/api/* JSON contract for the BAS Lite React SPA (formerly VOLTTRON agent)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request
from pydantic import BaseModel

from easy_aso.bacnet_client.jsonrpc_client import JsonRpcBacnetClient
from easy_aso.supervisor.coordinator import SupervisorCoordinator

logger = logging.getLogger(__name__)

router = APIRouter()

SCHEDULE_PATH = Path(os.environ.get("BAS_LITE_SCHEDULE_PATH", "/data/schedule.json"))
DRIVER_CFG_DIR = Path(os.environ.get("BAS_LITE_DRIVER_CONFIG_DIR", "/data/driver_configs"))
TREND_INTERVAL_SEC = float(os.environ.get("BAS_LITE_TREND_SAMPLE_SEC", "60"))
TREND_MAX = int(os.environ.get("BAS_LITE_TREND_MAX_SAMPLES", "1440"))


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


async def _snapshot_trends(app: Any) -> None:
    """Background: sample all point last_value into ring buffers."""
    await asyncio.sleep(3)
    while True:
        try:
            coord: SupervisorCoordinator = app.state.coordinator
            devices = await coord.list_devices(enabled_only=False)
            buf: Dict[str, Deque[dict[str, Any]]] = app.state.trend_buffers
            ts = _utc()
            for d in devices:
                pts = await coord.list_points(d.id, enabled_only=False)
                for p in pts:
                    entry = {"t": ts, "value": p.decoded_value()}
                    buf[p.id].append(entry)
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
        SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)
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
        "volttron": {
            "status": "not_applicable",
            "subscriptions": [],
            "note": "Stack is Docker + easy-aso (no VOLTTRON).",
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
    return {"items": []}


@router.get("/alarms/definitions")
async def alarm_definitions() -> dict:
    return {"items": []}


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
        return json.loads(SCHEDULE_PATH.read_text(encoding="utf-8"))
    return {
        "version": 1,
        "label": "Default",
        "weekly": {},
        "holidays": [],
        "linkedPoints": [],
    }


@router.post("/schedule")
async def schedule_post(body: dict = Body(...)) -> dict:
    SCHEDULE_PATH.write_text(json.dumps(body, indent=2), encoding="utf-8")
    return {"status": "ok"}


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


@router.get("/agents/vctl")
async def agents_vctl() -> dict:
    return {
        "exitCode": 0,
        "stderr": "",
        "stdout": "Docker + easy-aso — no vctl.\n",
        "agents": [],
        "vctlPath": None,
        "volttronRoot": None,
        "volttronHome": None,
        "note": "Use `docker compose ps` and `docker compose logs` instead.",
    }


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
    return {"items": []}


@router.get("/notifications/config")
async def notifications_config() -> dict:
    return {"smtp": {}, "emailNotificationSupported": False, "note": "Not configured in Docker BAS Lite."}


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
