import collections
import datetime as dt
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from copy import deepcopy
from urllib.parse import parse_qs

import volttron.utils as utils
from volttron.client.vip.agent import Agent, Core

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = "0.9.0"
PLATFORM_DRIVER_IDENTITY = "platform.driver"
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)


def utc_now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def default_weekly_schedule():
    days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    out = {}
    for d in days:
        if d in ("mon", "tue", "wed", "thu", "fri"):
            out[d] = {"occupied": True, "startMinutes": 8 * 60, "endMinutes": 17 * 60}
        else:
            out[d] = {"occupied": False, "startMinutes": 0, "endMinutes": 24 * 60}
    return {"version": 1, "label": "Default occupancy", "weekly": out, "holidays": [], "linkedPoints": []}


def _read_proc_loadavg():
    try:
        with open("/proc/loadavg", "r", encoding="utf-8") as f:
            p = f.read().split()
        return {"load1": float(p[0]), "load5": float(p[1]), "load15": float(p[2])}
    except Exception:
        return {"load1": None, "load5": None, "load15": None}


def _read_proc_mem():
    try:
        data = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                if ":" in line:
                    k, v = line.split(":", 1)
                    data[k.strip()] = int(v.split()[0]) * 1024
        total = data.get("MemTotal")
        avail = data.get("MemAvailable") or data.get("MemFree")
        used = (total - avail) if total and avail else None
        return {"memTotalBytes": total, "memAvailableBytes": avail, "memUsedBytes": used}
    except Exception:
        return {"memTotalBytes": None, "memAvailableBytes": None, "memUsedBytes": None}


def _disk_root():
    try:
        u = shutil.disk_usage("/")
        return {
            "path": "/",
            "totalBytes": u.total,
            "usedBytes": u.used,
            "freeBytes": u.free,
            "usedPercent": round(100.0 * u.used / u.total, 2) if u.total else None,
        }
    except Exception:
        return {"path": "/", "totalBytes": None, "usedBytes": None, "freeBytes": None, "usedPercent": None}


def _cpu_percent_simple():
    try:
        import psutil  # type: ignore

        return round(psutil.cpu_percent(interval=0.15), 2)
    except Exception:
        return None


def app8_web_agent(config_path, **kwargs):
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}
    return App8WebAgent(config=config, **kwargs)


class App8WebAgent(Agent):
    def __init__(self, config=None, **kwargs):
        super(App8WebAgent, self).__init__(enable_web=True, **kwargs)
        self.config = config or {}
        self.route_prefix = self.config.get("route_prefix", "/app8").rstrip("/")
        self.app_title = self.config.get("app_title", "BAS Lite on VOLTTRON")
        self.site_name = self.config.get("site_name", "unknown-site")
        self.max_trend_samples = int(self.config.get("max_trend_samples", 9500))
        self.trend_interval_minutes = int(self.config.get("trend_interval_minutes", 5))
        self.default_trend_retention_days = int(self.config.get("default_trend_retention_days", 31))
        self.webroot = os.path.abspath(os.path.join(os.path.dirname(__file__), "webroot"))
        self.bacnet_devices = list(self.config.get("bacnet_devices") or ["BensFakeAHU", "Zone1VAV"])
        self.volttron_root = self.config.get("volttron_root") or os.environ.get("VOLTTRON_ROOT") or os.path.expanduser("~/volttron")
        self.vctl_path = self.config.get("vctl_path") or os.path.join(self.volttron_root, "env", "bin", "vctl")
        self.allow_agent_lifecycle = bool(self.config.get("allow_agent_lifecycle", True))
        self.allow_driver_config_writes = bool(self.config.get("allow_driver_config_writes", True))
        self._volttron_home = self.config.get("volttron_home") or os.environ.get("VOLTTRON_HOME") or os.path.expanduser("~/.volttron")
        self._schedule_path = self.config.get("schedule_path") or os.path.join(os.path.dirname(__file__), "schedule_store.json")
        self._driver_store_root = self.config.get("driver_store_root", "/tmp/app8_driver_store")

        self.devices = {
            "BensFakeAHU": {
                "id": "BensFakeAHU",
                "name": "BensFakeAHU",
                "displayName": "Bens Fake AHU",
                "kind": "ahu",
                "address": "192.168.204.13",
                "deviceId": 3456789,
                "status": "unknown",
                "pollingEnabled": True,
                "lastSeen": None,
                "points": {},
            },
            "Zone1VAV": {
                "id": "Zone1VAV",
                "name": "Zone1VAV",
                "displayName": "Zone 1 VAV",
                "kind": "vav",
                "address": "192.168.204.14",
                "deviceId": 3456790,
                "status": "unknown",
                "pollingEnabled": True,
                "lastSeen": None,
                "points": {},
            },
        }
        self.point_meta = self._build_point_meta()
        self.trends = {point_id: collections.deque(maxlen=self.max_trend_samples) for point_id in self.point_meta}
        self.notification_logs = [{"timestamp": utc_now_iso(), "channel": "smtp", "recipient": "ops@example.local", "eventId": None, "status": "configured-not-sending", "error": None}]
        self.alarm_definitions = [
            {
                "id": "zone-temp-high",
                "name": "Zone temperature high",
                "enabled": True,
                "deviceId": "Zone1VAV",
                "pointId": "Zone1VAV::ZoneTemp",
                "severity": "warning",
                "conditionType": "greaterThanSetpointPlusOffset",
                "condition": {"referencePointId": "Zone1VAV::ZoneCoolingSpt", "offset": 1.0},
                "messageTemplate": "Zone 1 VAV temperature high",
                "persistenceSeconds": 0,
                "notifyChannels": ["smtp"],
            },
            {
                "id": "ahu-fan-status-failure",
                "name": "AHU fan status failure",
                "enabled": True,
                "deviceId": "BensFakeAHU",
                "pointId": "BensFakeAHU::SF_S",
                "severity": "critical",
                "conditionType": "boolFalse",
                "condition": {},
                "messageTemplate": "AHU supply fan status is false",
                "persistenceSeconds": 0,
                "notifyChannels": ["smtp"],
            },
        ]
        self.smtp_config = {"enabled": False, "host": "smtp.example.local", "port": 587, "from": "alerts@example.local", "to": ["ops@example.local"], "mode": "bench-placeholder"}
        self.last_publish_at = None

    def _build_point_meta(self):
        return {
            "BensFakeAHU::OA_T": {"pointId": "BensFakeAHU::OA_T", "deviceId": "BensFakeAHU", "name": "OA_T", "label": "Outdoor Air Temp", "units": "degF", "kind": "analog", "adjustable": False, "graphicGroup": "overview"},
            "BensFakeAHU::SA_T": {"pointId": "BensFakeAHU::SA_T", "deviceId": "BensFakeAHU", "name": "SA_T", "label": "Supply Air Temp", "units": "degF", "kind": "analog", "adjustable": False, "graphicGroup": "ahu"},
            "BensFakeAHU::SAT_SP": {"pointId": "BensFakeAHU::SAT_SP", "deviceId": "BensFakeAHU", "name": "SAT_SP", "label": "Supply Air Temp Setpoint", "units": "degF", "kind": "analog", "adjustable": True, "graphicGroup": "ahu"},
            "BensFakeAHU::DPR_O": {"pointId": "BensFakeAHU::DPR_O", "deviceId": "BensFakeAHU", "name": "DPR_O", "label": "Damper Output", "units": "%", "kind": "analog", "adjustable": False, "graphicGroup": "ahu"},
            "BensFakeAHU::SF_S": {"pointId": "BensFakeAHU::SF_S", "deviceId": "BensFakeAHU", "name": "SF_S", "label": "Supply Fan Status", "units": "bool", "kind": "binary", "adjustable": False, "graphicGroup": "ahu"},
            "Zone1VAV::ZoneTemp": {"pointId": "Zone1VAV::ZoneTemp", "deviceId": "Zone1VAV", "name": "ZoneTemp", "label": "Zone Temperature", "units": "degF", "kind": "analog", "adjustable": False, "graphicGroup": "vav"},
            "Zone1VAV::ZoneCoolingSpt": {"pointId": "Zone1VAV::ZoneCoolingSpt", "deviceId": "Zone1VAV", "name": "ZoneCoolingSpt", "label": "Zone Cooling Setpoint", "units": "degF", "kind": "analog", "adjustable": True, "graphicGroup": "vav"},
            "Zone1VAV::VAVFlow": {"pointId": "Zone1VAV::VAVFlow", "deviceId": "Zone1VAV", "name": "VAVFlow", "label": "Airflow", "units": "CFM", "kind": "analog", "adjustable": False, "graphicGroup": "vav"},
            "Zone1VAV::VAVFlowSpt": {"pointId": "Zone1VAV::VAVFlowSpt", "deviceId": "Zone1VAV", "name": "VAVFlowSpt", "label": "Airflow Setpoint", "units": "CFM", "kind": "analog", "adjustable": True, "graphicGroup": "vav"},
            "Zone1VAV::VAVDamperCmd": {"pointId": "Zone1VAV::VAVDamperCmd", "deviceId": "Zone1VAV", "name": "VAVDamperCmd", "label": "Damper Command", "units": "%", "kind": "analog", "adjustable": False, "graphicGroup": "vav"},
            "Zone1VAV::ZoneDemand": {"pointId": "Zone1VAV::ZoneDemand", "deviceId": "Zone1VAV", "name": "ZoneDemand", "label": "Zone Demand", "units": "%", "kind": "analog", "adjustable": False, "graphicGroup": "vav"},
        }

    def _run_vctl(self, args, timeout=120):
        if not os.path.isfile(self.vctl_path):
            return "", "vctl not found", 127
        cmd = [self.vctl_path] + list(args)
        env = os.environ.copy()
        env["VOLTTRON_HOME"] = self._volttron_home
        try:
            p = subprocess.run(cmd, cwd=self.volttron_root, env=env, capture_output=True, text=True, timeout=timeout)
            return p.stdout or "", p.stderr or "", p.returncode
        except Exception as exc:
            return "", str(exc), 1

    def _query_params(self, env):
        return parse_qs(env.get("QUERY_STRING", "")) if env else {}

    def _safe_float(self, v):
        try:
            return float(v)
        except Exception:
            return None

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        _log.info("Starting app8 web agent route=%s webroot=%s", self.route_prefix, self.webroot)
        self.vip.web.register_path(self.route_prefix, self.webroot)
        p = self.route_prefix
        self.vip.web.register_endpoint(p + "/api/health", callback=self.health_endpoint)
        self.vip.web.register_endpoint(p + "/api/devices", callback=self.devices_endpoint)
        self.vip.web.register_endpoint(p + "/api/points", callback=self.points_endpoint)
        self.vip.web.register_endpoint(p + "/api/polling", callback=self.polling_endpoint)
        self.vip.web.register_endpoint(p + "/api/alarms/definitions", callback=self.alarm_definitions_endpoint)
        self.vip.web.register_endpoint(p + "/api/alarms/events", callback=self.alarm_events_endpoint)
        self.vip.web.register_endpoint(p + "/api/trends", callback=self.trends_endpoint)
        self.vip.web.register_endpoint(p + "/api/notifications/logs", callback=self.notification_logs_endpoint)
        self.vip.web.register_endpoint(p + "/api/graphics/overview", callback=self.graphics_overview_endpoint)
        self.vip.web.register_endpoint(p + "/api/notifications/config", callback=self.notifications_config_endpoint)
        self.vip.web.register_endpoint(p + "/api/setpoints", callback=self.setpoints_endpoint)
        self.vip.web.register_endpoint(p + "/api/setpoints/write", callback=self.setpoint_write_endpoint)
        self.vip.web.register_endpoint(p + "/api/system/metrics", callback=self.system_metrics_endpoint)
        self.vip.web.register_endpoint(p + "/api/agents/vctl", callback=self.agents_vctl_endpoint)
        self.vip.web.register_endpoint(p + "/api/agents/lifecycle", callback=self.agents_lifecycle_endpoint)
        self.vip.web.register_endpoint(p + "/api/driver/configs", callback=self.driver_configs_endpoint)
        self.vip.web.register_endpoint(p + "/api/driver/config", callback=self.driver_config_get_endpoint)
        self.vip.web.register_endpoint(p + "/api/driver/config/store", callback=self.driver_config_store_endpoint)
        self.vip.web.register_endpoint(p + "/api/driver/config/delete", callback=self.driver_config_delete_endpoint)
        self.vip.web.register_endpoint(p + "/api/schedule", callback=self.schedule_endpoint)
        for d in self.bacnet_devices:
            self.vip.pubsub.subscribe(peer="pubsub", prefix="devices/%s/all" % d, callback=self._handle_publish)

    def _handle_publish(self, peer, sender, bus, topic, headers, message):
        try:
            payload = message[0] if isinstance(message, list) and message else message
            meta = message[1] if isinstance(message, list) and len(message) > 1 and isinstance(message[1], dict) else {}
            if not isinstance(payload, dict):
                return
            did = topic.split("/")[1]
            if did not in self.devices:
                self.devices[did] = {"id": did, "name": did, "displayName": did, "kind": "equipment", "address": "", "deviceId": 0, "status": "unknown", "pollingEnabled": True, "lastSeen": None, "points": {}}
            dev = self.devices[did]
            ts = headers.get("TimeStamp") if isinstance(headers, dict) else None
            ts = ts or utc_now_iso()
            dev["lastSeen"] = ts
            dev["status"] = "online"
            for point_name, value in payload.items():
                point_id = "%s::%s" % (did, point_name)
                units = meta.get(point_name, {}).get("units") if point_name in meta else None
                dev["points"][point_name] = {"value": value, "lastUpdated": ts, "units": units}
                if point_id in self.trends:
                    self.trends[point_id].append({"ts": ts, "value": value})
            self.last_publish_at = ts
        except Exception:
            _log.exception("publish processing failed")

    def _device_summary(self, d):
        status = d["status"]
        if self._device_alarm_state(d) == "alarm":
            status = "alarm"
        return {"id": d["id"], "name": d["name"], "displayName": d["displayName"], "kind": d["kind"], "address": d["address"], "deviceId": d["deviceId"], "status": status, "lastSeen": d["lastSeen"], "pollingEnabled": d["pollingEnabled"], "pointCount": len(d["points"])}

    def _point_record(self, point_id, meta):
        d = self.devices.get(meta["deviceId"]) or {"points": {}}
        runtime = d["points"].get(meta["name"], {})
        return {
            "id": point_id,
            "deviceId": meta["deviceId"],
            "name": meta["name"],
            "label": meta["label"],
            "units": meta["units"],
            "kind": meta["kind"],
            "value": runtime.get("value"),
            "lastUpdated": runtime.get("lastUpdated"),
            "alarmState": self._point_alarm_state(point_id),
            "trendEnabled": point_id in self.trends,
            "adjustable": meta.get("adjustable", False),
            "graphicGroup": meta.get("graphicGroup"),
        }

    def _device_alarm_state(self, d):
        if d["id"] == "Zone1VAV":
            zt = self._safe_float(d["points"].get("ZoneTemp", {}).get("value"))
            zs = self._safe_float(d["points"].get("ZoneCoolingSpt", {}).get("value"))
            if zt is not None and zs is not None and zt > zs + 1.0:
                return "alarm"
        if d["id"] == "BensFakeAHU":
            sf = d["points"].get("SF_S", {}).get("value")
            if sf in (0, False, "0", "false", "False"):
                return "alarm"
        return "normal"

    def _point_alarm_state(self, point_id):
        if point_id == "Zone1VAV::ZoneTemp":
            zt = self._safe_float(self.devices.get("Zone1VAV", {}).get("points", {}).get("ZoneTemp", {}).get("value"))
            zs = self._safe_float(self.devices.get("Zone1VAV", {}).get("points", {}).get("ZoneCoolingSpt", {}).get("value"))
            if zt is not None and zs is not None and zt > zs + 1.0:
                return "alarm"
        if point_id == "BensFakeAHU::SF_S":
            sf = self.devices.get("BensFakeAHU", {}).get("points", {}).get("SF_S", {}).get("value")
            if sf in (0, False, "0", "false", "False"):
                return "alarm"
        return "normal"

    def _alarm_events(self):
        out = []
        zt = self._safe_float(self.devices.get("Zone1VAV", {}).get("points", {}).get("ZoneTemp", {}).get("value"))
        zs = self._safe_float(self.devices.get("Zone1VAV", {}).get("points", {}).get("ZoneCoolingSpt", {}).get("value"))
        if zt is not None and zs is not None and zt > zs + 1.0:
            out.append({"id": "evt-zone-temp-high", "alarmDefinitionId": "zone-temp-high", "deviceId": "Zone1VAV", "pointId": "Zone1VAV::ZoneTemp", "severity": "warning", "state": "active", "message": "Zone temperature high", "triggeredAt": self.devices.get("Zone1VAV", {}).get("points", {}).get("ZoneTemp", {}).get("lastUpdated") or utc_now_iso()})
        sf = self.devices.get("BensFakeAHU", {}).get("points", {}).get("SF_S", {}).get("value")
        if sf in (0, False, "0", "false", "False"):
            out.append({"id": "evt-ahu-fan-status-failure", "alarmDefinitionId": "ahu-fan-status-failure", "deviceId": "BensFakeAHU", "pointId": "BensFakeAHU::SF_S", "severity": "critical", "state": "active", "message": "AHU supply fan status failure", "triggeredAt": self.devices.get("BensFakeAHU", {}).get("points", {}).get("SF_S", {}).get("lastUpdated") or utc_now_iso()})
        return out

    def health_endpoint(self, env, data):
        return {"status": "ok", "appTitle": self.app_title, "siteName": self.site_name, "routePrefix": self.route_prefix, "agentIdentity": self.core.identity, "lastPublishAt": self.last_publish_at, "defaultTrendPointId": "Zone1VAV::ZoneTemp", "counts": {"devices": len(self.devices), "points": len(self.point_meta), "activeAlarms": len(self._alarm_events())}, "trendPolicy": {"intervalMinutes": self.trend_interval_minutes, "retentionDays": self.default_trend_retention_days, "maxSamplesPerPoint": self.max_trend_samples}, "volttron": {"status": "connected", "subscriptions": ["devices/%s/all" % d for d in self.bacnet_devices]}}

    def devices_endpoint(self, env, data):
        return {"items": [self._device_summary(d) for d in self.devices.values()]}

    def points_endpoint(self, env, data):
        params = self._query_params(env)
        did = params.get("deviceId", [None])[0]
        items = [self._point_record(pid, m) for pid, m in self.point_meta.items()]
        if did:
            items = [i for i in items if i["deviceId"] == did]
        return {"items": items}

    def polling_endpoint(self, env, data):
        return {"devices": [{"deviceId": d["id"], "name": d["displayName"], "pollingEnabled": d["pollingEnabled"], "lastSeen": d["lastSeen"]} for d in self.devices.values()]}

    def alarm_definitions_endpoint(self, env, data):
        return {"items": deepcopy(self.alarm_definitions)}

    def alarm_events_endpoint(self, env, data):
        return {"items": self._alarm_events()}

    def trends_endpoint(self, env, data):
        params = self._query_params(env)
        point_id = params.get("pointId", ["Zone1VAV::ZoneTemp"])[0]
        if point_id not in self.trends:
            point_id = "Zone1VAV::ZoneTemp"
        meta = self.point_meta.get(point_id, {})
        vals = [s["value"] for s in self.trends.get(point_id, []) if isinstance(s.get("value"), (int, float))]
        return {"pointId": point_id, "label": meta.get("label", point_id), "units": meta.get("units"), "retentionDays": self.default_trend_retention_days, "intervalMinutes": self.trend_interval_minutes, "items": list(self.trends.get(point_id, [])), "summary": {"latest": vals[-1] if vals else None, "min": min(vals) if vals else None, "max": max(vals) if vals else None, "avg": round(sum(vals) / len(vals), 2) if vals else None}}

    def notification_logs_endpoint(self, env, data):
        return {"items": deepcopy(self.notification_logs)}

    def notifications_config_endpoint(self, env, data):
        return {"smtp": deepcopy(self.smtp_config), "emailNotificationSupported": True, "note": "Bench placeholder; configure SMTP when needed."}

    def setpoints_endpoint(self, env, data):
        params = self._query_params(env)
        did = params.get("deviceId", [None])[0]
        items = [self._point_record(pid, m) for pid, m in self.point_meta.items() if m.get("adjustable")]
        if did:
            items = [i for i in items if i["deviceId"] == did]
        return {"items": items}

    def setpoint_write_endpoint(self, env, data):
        if not isinstance(data, dict):
            return {"status": "error", "message": "JSON body required"}
        point_id = data.get("pointId")
        raw = data.get("value")
        if point_id not in self.point_meta:
            return {"status": "error", "message": "Unknown pointId: %s" % point_id}
        meta = self.point_meta[point_id]
        if not meta.get("adjustable"):
            return {"status": "error", "message": "Point not adjustable: %s" % point_id}
        try:
            value = float(raw) if meta["kind"] == "analog" else raw
            result = self.vip.rpc.call(PLATFORM_DRIVER_IDENTITY, "set_point", meta["deviceId"], meta["name"], value).get(timeout=15)
            now = utc_now_iso()
            self.notification_logs.append({"timestamp": now, "channel": "write", "recipient": meta["deviceId"], "eventId": point_id, "status": "setpoint-write-ok:%s" % value, "error": None})
            self.notification_logs = self.notification_logs[-100:]
            return {"status": "ok", "pointId": point_id, "deviceId": meta["deviceId"], "pointName": meta["name"], "requestedValue": value, "result": result, "timestamp": now}
        except Exception as exc:
            return {"status": "error", "pointId": point_id, "message": str(exc)}

    def graphics_overview_endpoint(self, env, data):
        return {"systemOverview": {"siteName": self.site_name, "equipment": [self._device_summary(d) for d in self.devices.values()]}, "equipmentGraphics": {"ahu": {"deviceId": "BensFakeAHU", "points": [self._point_record(pid, m) for pid, m in self.point_meta.items() if m["deviceId"] == "BensFakeAHU"]}, "vav": {"deviceId": "Zone1VAV", "points": [self._point_record(pid, m) for pid, m in self.point_meta.items() if m["deviceId"] == "Zone1VAV"]}}}

    def system_metrics_endpoint(self, env, data):
        return {"timestamp": utc_now_iso(), "cpuPercent": _cpu_percent_simple(), "loadavg": _read_proc_loadavg(), "memory": _read_proc_mem(), "diskRoot": _disk_root(), "hostname": os.uname().nodename if hasattr(os, "uname") else None}

    def agents_vctl_endpoint(self, env, data):
        out, err, code = self._run_vctl(["status"])
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        agents = []
        for line in lines:
            m = UUID_RE.search(line)
            if m:
                agents.append({"uuid": m.group(0), "summary": line})
            else:
                agents.append({"uuid": line[:24], "summary": line})
        return {"exitCode": code, "stdout": out, "stderr": err, "agents": agents}

    def agents_lifecycle_endpoint(self, env, data):
        if not self.allow_agent_lifecycle:
            return {"status": "error", "message": "Agent lifecycle disabled"}
        if not isinstance(data, dict):
            return {"status": "error", "message": "JSON body required"}
        action = str(data.get("action", "")).strip().lower()
        tag = data.get("tag")
        uid = data.get("uuid")
        if action not in ("start", "stop", "restart", "remove"):
            return {"status": "error", "message": "Unsupported action"}
        target = uid or tag
        if not target:
            return {"status": "error", "message": "uuid or tag required"}
        args = [action, target]
        if action in ("start", "stop", "restart", "remove"):
            args = [action, "--uuid", uid] if uid else [action, "--tag", tag]
        out, err, code = self._run_vctl(args)
        return {"status": "ok" if code == 0 else "error", "stdout": out, "stderr": err, "exitCode": code}

    def _driver_path(self, name):
        root = os.path.abspath(self._driver_store_root)
        n = (name or "").strip().replace("\\", "/")
        n = n.lstrip("/")
        fp = os.path.abspath(os.path.join(root, n))
        if not fp.startswith(root):
            raise ValueError("Invalid path")
        return root, fp

    def _driver_list_local(self):
        names = []
        root = os.path.abspath(self._driver_store_root)
        if not os.path.isdir(root):
            return names
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                p = os.path.join(dirpath, fn)
                names.append(os.path.relpath(p, root).replace("\\", "/"))
        names.sort()
        return names

    def driver_configs_endpoint(self, env, data):
        out, err, code = self._run_vctl(["config", "list", PLATFORM_DRIVER_IDENTITY], timeout=60)
        if code != 0:
            items = self._driver_list_local()
            return {"items": items, "stderr": err, "exitCode": code}
        items = [ln.strip() for ln in out.splitlines() if ln.strip()]
        return {"items": items, "stderr": err, "exitCode": code}

    def driver_config_get_endpoint(self, env, data):
        params = self._query_params(env)
        name = params.get("name", [""])[0]
        if not name:
            return {"name": name, "content": "", "stderr": "Missing name", "exitCode": 1}
        out, err, code = self._run_vctl(["config", "get", PLATFORM_DRIVER_IDENTITY, name], timeout=60)
        if code != 0:
            try:
                _, fp = self._driver_path(name)
                with open(fp, "r", encoding="utf-8") as f:
                    out = f.read()
                code = 0
                err = ""
            except Exception as exc:
                err = ("%s\n%s" % (err, exc)).strip()
        return {"name": name, "content": out, "stderr": err, "exitCode": code}

    def driver_config_store_endpoint(self, env, data):
        if not self.allow_driver_config_writes:
            return {"status": "error", "message": "Driver config writes disabled"}
        if not isinstance(data, dict):
            return {"status": "error", "message": "JSON body required"}
        name = str(data.get("name", "")).strip()
        content = str(data.get("content", ""))
        as_csv = bool(data.get("csv", False))
        if not name:
            return {"status": "error", "message": "name required"}
        args = ["config", "store", PLATFORM_DRIVER_IDENTITY, name, content]
        if as_csv:
            args.append("--csv")
        out, err, code = self._run_vctl(args, timeout=60)
        if code != 0:
            try:
                root, fp = self._driver_path(name)
                os.makedirs(os.path.dirname(fp), exist_ok=True)
                os.makedirs(root, exist_ok=True)
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(content)
                code = 0
                err = ""
                out = "stored-local-fallback"
            except Exception as exc:
                err = ("%s\n%s" % (err, exc)).strip()
        return {"status": "ok" if code == 0 else "error", "stdout": out, "stderr": err, "exitCode": code}

    def driver_config_delete_endpoint(self, env, data):
        if not self.allow_driver_config_writes:
            return {"status": "error", "message": "Driver config writes disabled"}
        if not isinstance(data, dict):
            return {"status": "error", "message": "JSON body required"}
        name = str(data.get("name", "")).strip()
        if not name:
            return {"status": "error", "message": "name required"}
        out, err, code = self._run_vctl(["config", "delete", PLATFORM_DRIVER_IDENTITY, name], timeout=60)
        if code != 0:
            try:
                _, fp = self._driver_path(name)
                if os.path.isfile(fp):
                    os.remove(fp)
                code = 0
                err = ""
                out = "deleted-local-fallback"
            except Exception as exc:
                err = ("%s\n%s" % (err, exc)).strip()
        return {"status": "ok" if code == 0 else "error", "stdout": out, "stderr": err, "exitCode": code}

    def schedule_endpoint(self, env, data):
        method = (env or {}).get("REQUEST_METHOD", "GET").upper()
        if method == "POST":
            if not isinstance(data, dict):
                return {"status": "error", "message": "JSON body required"}
            try:
                os.makedirs(os.path.dirname(self._schedule_path), exist_ok=True)
                with open(self._schedule_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, sort_keys=True)
                return data
            except Exception as exc:
                return {"status": "error", "message": str(exc)}
        try:
            with open(self._schedule_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default_weekly_schedule()


def main(argv=sys.argv):
    utils.vip_main(app8_web_agent, version=__version__)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
