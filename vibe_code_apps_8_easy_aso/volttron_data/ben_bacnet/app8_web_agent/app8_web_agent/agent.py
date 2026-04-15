import collections
import datetime as dt
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from copy import deepcopy
from urllib.parse import parse_qs

from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1.0'
PLATFORM_DRIVER_IDENTITY = 'platform.driver'
UUID_RE = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.I)


def utc_now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')


def app8_web_agent(config_path, **kwargs):
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}
    return App8WebAgent(config=config, **kwargs)


def _read_proc_loadavg():
    try:
        with open('/proc/loadavg', 'r', encoding='utf-8') as f:
            parts = f.read().split()
        return {'load1': float(parts[0]), 'load5': float(parts[1]), 'load15': float(parts[2])}
    except Exception:
        return {'load1': None, 'load5': None, 'load15': None}


def _read_proc_mem():
    try:
        data = {}
        with open('/proc/meminfo', 'r', encoding='utf-8') as f:
            for line in f:
                if ':' in line:
                    k, v = line.split(':', 1)
                    data[k.strip()] = int(v.split()[0]) * 1024
        total = data.get('MemTotal')
        avail = data.get('MemAvailable') or data.get('MemFree')
        used = (total - avail) if total and avail else None
        return {
            'memTotalBytes': total,
            'memAvailableBytes': avail,
            'memUsedBytes': used,
        }
    except Exception:
        return {'memTotalBytes': None, 'memAvailableBytes': None, 'memUsedBytes': None}


def _disk_root():
    try:
        u = shutil.disk_usage('/')
        return {
            'path': '/',
            'totalBytes': u.total,
            'usedBytes': u.used,
            'freeBytes': u.free,
            'usedPercent': round(100.0 * u.used / u.total, 2) if u.total else None,
        }
    except Exception:
        return {'path': '/', 'totalBytes': None, 'usedBytes': None, 'freeBytes': None, 'usedPercent': None}


def _cpu_percent_simple():
    try:
        import psutil  # type: ignore
        return round(psutil.cpu_percent(interval=0.15), 2)
    except Exception:
        return None


def default_weekly_schedule():
    days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
    out = {}
    for d in days:
        if d in ('mon', 'tue', 'wed', 'thu', 'fri'):
            out[d] = {'occupied': True, 'startMinutes': 8 * 60, 'endMinutes': 17 * 60}
        else:
            out[d] = {'occupied': False, 'startMinutes': 0, 'endMinutes': 24 * 60}
    return {
        'version': 1,
        'label': 'Default occupancy',
        'weekly': out,
        'holidays': [],
        'linkedPoints': [],
    }


def _bench_site_bundle():
    """Built-in demo site (two BACnet devices) — same as original App 8 bench."""
    devices = {
        'BensFakeAHU': {
            'id': 'BensFakeAHU',
            'name': 'BensFakeAHU',
            'displayName': 'Bens Fake AHU',
            'kind': 'ahu',
            'address': '192.168.204.13',
            'deviceId': 3456789,
            'status': 'unknown',
            'pollingEnabled': True,
            'lastSeen': None,
            'points': {}
        },
        'Zone1VAV': {
            'id': 'Zone1VAV',
            'name': 'Zone1VAV',
            'displayName': 'Zone 1 VAV',
            'kind': 'vav',
            'address': '192.168.204.14',
            'deviceId': 3456790,
            'status': 'unknown',
            'pollingEnabled': True,
            'lastSeen': None,
            'points': {}
        },
    }
    point_meta = {
        'BensFakeAHU::OA_T': {'pointId': 'BensFakeAHU::OA_T', 'deviceId': 'BensFakeAHU', 'name': 'OA_T', 'label': 'Outdoor Air Temp', 'units': '°F', 'kind': 'analog', 'adjustable': False, 'graphicGroup': 'overview'},
        'BensFakeAHU::SA_T': {'pointId': 'BensFakeAHU::SA_T', 'deviceId': 'BensFakeAHU', 'name': 'SA_T', 'label': 'Supply Air Temp', 'units': '°F', 'kind': 'analog', 'adjustable': False, 'graphicGroup': 'ahu'},
        'BensFakeAHU::SAT_SP': {'pointId': 'BensFakeAHU::SAT_SP', 'deviceId': 'BensFakeAHU', 'name': 'SAT_SP', 'label': 'Supply Air Temp Setpoint', 'units': '°F', 'kind': 'analog', 'adjustable': True, 'graphicGroup': 'ahu'},
        'BensFakeAHU::DPR_O': {'pointId': 'BensFakeAHU::DPR_O', 'deviceId': 'BensFakeAHU', 'name': 'DPR_O', 'label': 'Damper Output', 'units': '%', 'kind': 'analog', 'adjustable': False, 'graphicGroup': 'ahu'},
        'BensFakeAHU::SF_S': {'pointId': 'BensFakeAHU::SF_S', 'deviceId': 'BensFakeAHU', 'name': 'SF_S', 'label': 'Supply Fan Status', 'units': 'bool', 'kind': 'binary', 'adjustable': False, 'graphicGroup': 'ahu'},
        'Zone1VAV::ZoneTemp': {'pointId': 'Zone1VAV::ZoneTemp', 'deviceId': 'Zone1VAV', 'name': 'ZoneTemp', 'label': 'Zone Temperature', 'units': '°F', 'kind': 'analog', 'adjustable': False, 'graphicGroup': 'vav'},
        'Zone1VAV::ZoneCoolingSpt': {'pointId': 'Zone1VAV::ZoneCoolingSpt', 'deviceId': 'Zone1VAV', 'name': 'ZoneCoolingSpt', 'label': 'Zone Cooling Setpoint', 'units': '°F', 'kind': 'analog', 'adjustable': True, 'graphicGroup': 'vav'},
        'Zone1VAV::VAVFlow': {'pointId': 'Zone1VAV::VAVFlow', 'deviceId': 'Zone1VAV', 'name': 'VAVFlow', 'label': 'Airflow', 'units': 'CFM', 'kind': 'analog', 'adjustable': False, 'graphicGroup': 'vav'},
        'Zone1VAV::VAVFlowSpt': {'pointId': 'Zone1VAV::VAVFlowSpt', 'deviceId': 'Zone1VAV', 'name': 'VAVFlowSpt', 'label': 'Airflow Setpoint', 'units': 'CFM', 'kind': 'analog', 'adjustable': True, 'graphicGroup': 'vav'},
        'Zone1VAV::VAVDamperCmd': {'pointId': 'Zone1VAV::VAVDamperCmd', 'deviceId': 'Zone1VAV', 'name': 'VAVDamperCmd', 'label': 'Damper Command', 'units': '%', 'kind': 'analog', 'adjustable': False, 'graphicGroup': 'vav'},
        'Zone1VAV::ZoneDemand': {'pointId': 'Zone1VAV::ZoneDemand', 'deviceId': 'Zone1VAV', 'name': 'ZoneDemand', 'label': 'Zone Demand', 'units': '%', 'kind': 'analog', 'adjustable': False, 'graphicGroup': 'vav'},
    }
    alarm_definitions = [
        {
            'id': 'zone-temp-high',
            'name': 'Zone temperature high',
            'enabled': True,
            'deviceId': 'Zone1VAV',
            'pointId': 'Zone1VAV::ZoneTemp',
            'severity': 'warning',
            'conditionType': 'greaterThanSetpointPlusOffset',
            'condition': {'referencePointId': 'Zone1VAV::ZoneCoolingSpt', 'offset': 1.0},
            'messageTemplate': 'Zone 1 VAV temperature high: {value:.1f} vs setpoint {ref:.1f}',
            'persistenceSeconds': 0,
            'notifyChannels': ['smtp']
        },
        {
            'id': 'ahu-fan-status-failure',
            'name': 'AHU fan status failure',
            'enabled': True,
            'deviceId': 'BensFakeAHU',
            'pointId': 'BensFakeAHU::SF_S',
            'severity': 'critical',
            'conditionType': 'boolFalse',
            'condition': {},
            'messageTemplate': 'AHU supply fan status is false',
            'persistenceSeconds': 0,
            'notifyChannels': ['smtp']
        },
    ]
    trend0 = sorted(point_meta.keys())[0]
    bacnet = ['BensFakeAHU', 'Zone1VAV']
    return devices, point_meta, alarm_definitions, bacnet, trend0


def load_site_model_from_config(cfg, agent_dir):
    """
    Optional site model for any building: JSON file and/or inline ``devices`` + ``points``.
    See ``site_model.example.json`` and ``docs/replicate-any-building-lan-topology.md``.
    """
    merged = {}
    path = cfg.get('site_model_path')
    if path:
        fp = path if os.path.isabs(path) else os.path.join(agent_dir, path)
        try:
            with open(fp, encoding='utf-8') as f:
                merged.update(json.load(f))
        except Exception as exc:
            _log.warning('Could not load site_model_path %r (%s); using built-in bench defaults', fp, exc)
            return None
    if isinstance(cfg.get('devices'), dict) and cfg.get('devices'):
        merged['devices'] = cfg['devices']
    if isinstance(cfg.get('points'), list) and cfg.get('points'):
        merged['points'] = cfg['points']
    if isinstance(cfg.get('alarm_definitions'), list):
        merged['alarm_definitions'] = cfg['alarm_definitions']
    devs = merged.get('devices')
    pts = merged.get('points')
    if not isinstance(devs, dict) or not devs or not isinstance(pts, list) or not pts:
        return None

    devices = {}
    for did, row in devs.items():
        if not isinstance(row, dict):
            continue
        d = deepcopy(row)
        d.setdefault('id', did)
        d.setdefault('name', did)
        d.setdefault('displayName', did)
        d.setdefault('kind', 'equipment')
        d.setdefault('address', '')
        d.setdefault('deviceId', 0)
        d.setdefault('status', 'unknown')
        d.setdefault('pollingEnabled', True)
        d.setdefault('lastSeen', None)
        d.setdefault('points', {})
        devices[str(d['id'])] = d

    point_meta = {}
    for p in pts:
        if not isinstance(p, dict) or not p.get('pointId') or not p.get('deviceId') or not p.get('name'):
            _log.warning('Skipping invalid point row: %s', p)
            continue
        pid = str(p['pointId'])
        point_meta[pid] = {
            'pointId': pid,
            'deviceId': str(p['deviceId']),
            'name': str(p['name']),
            'label': str(p.get('label', p['name'])),
            'units': str(p.get('units', '')),
            'kind': str(p.get('kind', 'analog')),
            'adjustable': bool(p.get('adjustable', False)),
            'graphicGroup': str(p.get('graphicGroup', 'default')),
        }

    alarm_definitions = list(merged.get('alarm_definitions') or [])
    bacnet = list(cfg.get('bacnet_devices') or list(devices.keys()))
    trend0 = str(cfg.get('default_trend_point_id') or sorted(point_meta.keys())[0])
    return devices, point_meta, alarm_definitions, bacnet, trend0


class App8WebAgent(Agent):
    def __init__(self, config=None, **kwargs):
        super(App8WebAgent, self).__init__(enable_web=True, **kwargs)
        self.config = config or {}
        self.route_prefix = self.config.get('route_prefix', '/app8').rstrip('/')
        self.app_title = self.config.get('app_title', 'BAS Lite on VOLTTRON')
        self.site_name = self.config.get('site_name', 'unknown-site')
        self.max_trend_samples = int(self.config.get('max_trend_samples', 9500))
        self.trend_interval_minutes = int(self.config.get('trend_interval_minutes', 5))
        self.default_trend_retention_days = int(self.config.get('default_trend_retention_days', 31))
        self.webroot = os.path.abspath(os.path.join(os.path.dirname(__file__), 'webroot'))
        agent_dir = os.path.dirname(__file__)
        site_bundle = load_site_model_from_config(self.config, agent_dir)
        if site_bundle:
            self.devices, self.point_meta, self.alarm_definitions, self.bacnet_devices, self._default_trend_point_id = site_bundle
            self.devices = deepcopy(self.devices)
        else:
            bd, pm, ad, bc, tp = _bench_site_bundle()
            self.devices = deepcopy(bd)
            self.point_meta = deepcopy(pm)
            self.alarm_definitions = deepcopy(ad)
            self.bacnet_devices = list(self.config.get('bacnet_devices') or bc)
            self._default_trend_point_id = str(self.config.get('default_trend_point_id') or tp)
        self.volttron_root = self.config.get('volttron_root') or os.environ.get('VOLTTRON_ROOT') or os.path.expanduser('~/volttron')
        self.vctl_path = self.config.get('vctl_path') or os.path.join(self.volttron_root, 'env', 'bin', 'vctl')
        self.allow_agent_lifecycle = bool(self.config.get('allow_agent_lifecycle', True))
        self.allow_driver_config_writes = bool(self.config.get('allow_driver_config_writes', True))
        self._volttron_home = os.environ.get('VOLTTRON_HOME') or os.path.expanduser('~/.volttron')
        self._schedule_path = os.path.join(os.path.dirname(__file__), 'schedule_store.json')

        self.trends = {point_id: collections.deque(maxlen=self.max_trend_samples) for point_id in self.point_meta}
        self.notification_logs = [
            {
                'timestamp': utc_now_iso(),
                'channel': 'smtp',
                'recipient': 'ops@example.local',
                'eventId': None,
                'status': 'configured-not-sending',
                'error': None
            }
        ]
        self.smtp_config = {
            'enabled': False,
            'host': 'smtp.example.local',
            'port': 587,
            'from': 'alerts@example.local',
            'to': ['ops@example.local'],
            'mode': 'bench-placeholder'
        }
        self.last_publish_at = None

    def _run_vctl(self, args, timeout=120):
        if not os.path.isfile(self.vctl_path):
            return '', f'vctl not found at {self.vctl_path}', 127
        cmd = [self.vctl_path] + list(args)
        env = os.environ.copy()
        env['VOLTTRON_HOME'] = self._volttron_home
        try:
            proc = subprocess.run(
                cmd,
                cwd=self.volttron_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return proc.stdout or '', proc.stderr or '', proc.returncode
        except subprocess.TimeoutExpired:
            return '', 'vctl command timed out', 124
        except Exception as exc:
            return '', str(exc), 1

    def _parse_vctl_agents(self, stdout):
        rows = []
        for line in (stdout or '').splitlines():
            line = line.strip()
            if not line or line.lower().startswith('uuid'):
                continue
            m = UUID_RE.search(line)
            if not m:
                continue
            uuid = m.group(0)
            rest = line.replace(uuid, '', 1).strip()
            rows.append({'uuid': uuid, 'summary': rest})
        return rows

    def _load_schedule(self):
        try:
            with open(self._schedule_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return default_weekly_schedule()

    def _save_schedule(self, data):
        with open(self._schedule_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        _log.info('Starting app8 web agent prefix=%s webroot=%s', self.route_prefix, self.webroot)
        self.vip.web.register_path(self.route_prefix, self.webroot)
        p = self.route_prefix
        self.vip.web.register_endpoint(p + '/api/health', callback=self.health_endpoint)
        self.vip.web.register_endpoint(p + '/api/devices', callback=self.devices_endpoint)
        self.vip.web.register_endpoint(p + '/api/points', callback=self.points_endpoint)
        self.vip.web.register_endpoint(p + '/api/polling', callback=self.polling_endpoint)
        self.vip.web.register_endpoint(p + '/api/alarms/definitions', callback=self.alarm_definitions_endpoint)
        self.vip.web.register_endpoint(p + '/api/alarms/events', callback=self.alarm_events_endpoint)
        self.vip.web.register_endpoint(p + '/api/trends', callback=self.trends_endpoint)
        self.vip.web.register_endpoint(p + '/api/notifications/logs', callback=self.notification_logs_endpoint)
        self.vip.web.register_endpoint(p + '/api/notifications/config', callback=self.notifications_config_endpoint)
        self.vip.web.register_endpoint(p + '/api/setpoints', callback=self.setpoints_endpoint)
        self.vip.web.register_endpoint(p + '/api/setpoints/write', callback=self.setpoint_write_endpoint)
        self.vip.web.register_endpoint(p + '/api/graphics/overview', callback=self.graphics_overview_endpoint)
        self.vip.web.register_endpoint(p + '/api/system/metrics', callback=self.system_metrics_endpoint)
        self.vip.web.register_endpoint(p + '/api/agents/vctl', callback=self.agents_vctl_endpoint)
        self.vip.web.register_endpoint(p + '/api/agents/lifecycle', callback=self.agents_lifecycle_endpoint)
        self.vip.web.register_endpoint(p + '/api/driver/configs', callback=self.driver_configs_list_endpoint)
        self.vip.web.register_endpoint(p + '/api/driver/config', callback=self.driver_config_get_endpoint)
        self.vip.web.register_endpoint(p + '/api/driver/config/store', callback=self.driver_config_store_endpoint)
        self.vip.web.register_endpoint(p + '/api/driver/config/delete', callback=self.driver_config_delete_endpoint)
        self.vip.web.register_endpoint(p + '/api/schedule', callback=self.schedule_endpoint)
        for name in self.bacnet_devices:
            topic = f'devices/{name}/all'
            self.vip.pubsub.subscribe(peer='pubsub', prefix=topic, callback=self._handle_publish)
            _log.info('Subscribed %s', topic)

    def _handle_publish(self, peer, sender, bus, topic, headers, message):
        try:
            payload = message[0] if isinstance(message, list) and message else message
            meta_payload = message[1] if isinstance(message, list) and len(message) > 1 and isinstance(message[1], dict) else {}
            if not isinstance(payload, dict):
                return
            parts = topic.split('/')
            device_name = parts[1] if len(parts) > 1 else None
            if not device_name or device_name not in self.devices:
                return
            device = self.devices[device_name]
            timestamp = headers.get('TimeStamp') if isinstance(headers, dict) else None
            timestamp = timestamp or utc_now_iso()
            device['lastSeen'] = timestamp
            device['status'] = 'online'
            for point_name, value in payload.items():
                point_id = f'{device_name}::{point_name}'
                units = meta_payload.get(point_name, {}).get('units') if point_name in meta_payload else None
                device['points'][point_name] = {
                    'value': value,
                    'lastUpdated': timestamp,
                    'units': units
                }
                if point_id in self.trends:
                    self.trends[point_id].append({'ts': timestamp, 'value': value})
            self.last_publish_at = timestamp
        except Exception as exc:
            _log.exception('Publish handler error topic=%s: %s', topic, exc)

    def _safe_float(self, value):
        try:
            return float(value)
        except Exception:
            return None

    def _query_params(self, env):
        return parse_qs(env.get('QUERY_STRING', '')) if env else {}

    def _device_summary(self, device):
        status = device['status']
        if self._device_alarm_state(device) == 'alarm':
            status = 'alarm'
        return {
            'id': device['id'],
            'name': device['name'],
            'displayName': device['displayName'],
            'kind': device['kind'],
            'address': device['address'],
            'deviceId': device['deviceId'],
            'status': status,
            'lastSeen': device['lastSeen'],
            'pollingEnabled': device['pollingEnabled'],
            'pointCount': len(device['points'])
        }

    def _point_record(self, point_id, meta):
        device = self.devices[meta['deviceId']]
        runtime = device['points'].get(meta['name'], {})
        alarm_state = self._point_alarm_state(point_id)
        return {
            'id': point_id,
            'deviceId': meta['deviceId'],
            'name': meta['name'],
            'label': meta['label'],
            'units': meta['units'],
            'kind': meta['kind'],
            'value': runtime.get('value'),
            'lastUpdated': runtime.get('lastUpdated'),
            'alarmState': alarm_state,
            'trendEnabled': point_id in self.trends,
            'adjustable': meta.get('adjustable', False),
            'graphicGroup': meta.get('graphicGroup')
        }

    def _point_raw_value(self, point_id):
        meta = self.point_meta.get(point_id)
        if not meta:
            return None
        dev = self.devices.get(meta['deviceId']) or {}
        pts = dev.get('points') or {}
        return pts.get(meta['name'], {}).get('value')

    def _alarm_def_is_active(self, ad):
        if not ad.get('enabled', True):
            return False
        ct = ad.get('conditionType')
        pid = ad.get('pointId')
        if not pid or not ct:
            return False
        if ct == 'greaterThanSetpointPlusOffset':
            ref = (ad.get('condition') or {}).get('referencePointId')
            if not ref:
                return False
            off = float((ad.get('condition') or {}).get('offset', 0))
            pv = self._safe_float(self._point_raw_value(pid))
            rv = self._safe_float(self._point_raw_value(ref))
            return pv is not None and rv is not None and pv > rv + off
        if ct == 'boolFalse':
            v = self._point_raw_value(pid)
            return v in (0, False, '0', 'false', 'False')
        return False

    def _alarm_message(self, ad):
        tpl = ad.get('messageTemplate') or ad.get('name') or ad.get('id') or 'Alarm'
        pid = ad.get('pointId')
        raw_v = self._point_raw_value(pid)
        ctx = {'value': raw_v, 'ref': None, 'offset': None}
        cond = ad.get('condition') or {}
        if ad.get('conditionType') == 'greaterThanSetpointPlusOffset':
            ref_id = cond.get('referencePointId')
            ctx['ref'] = self._point_raw_value(ref_id)
            ctx['offset'] = cond.get('offset')
        fv = self._safe_float(raw_v)
        fr = self._safe_float(ctx['ref'])
        fmt_ctx = {
            'value': fv if fv is not None else raw_v,
            'ref': fr if fr is not None else ctx['ref'],
            'offset': ctx['offset'],
        }
        try:
            return tpl.format(**fmt_ctx)
        except Exception:
            return tpl

    def _point_last_updated(self, point_id):
        meta = self.point_meta.get(point_id)
        if not meta:
            return utc_now_iso()
        dev = self.devices.get(meta['deviceId']) or {}
        pts = dev.get('points') or {}
        return pts.get(meta['name'], {}).get('lastUpdated') or utc_now_iso()

    def _device_alarm_state(self, device):
        for ad in self.alarm_definitions:
            if not ad.get('enabled', True):
                continue
            if ad.get('deviceId') != device.get('id'):
                continue
            if self._alarm_def_is_active(ad):
                return 'alarm'
        return 'normal'

    def _point_alarm_state(self, point_id):
        for ad in self.alarm_definitions:
            if not ad.get('enabled', True):
                continue
            if ad.get('pointId') != point_id:
                continue
            if self._alarm_def_is_active(ad):
                return 'alarm'
        return 'normal'

    def _alarm_events(self):
        events = []
        seen = set()
        for ad in self.alarm_definitions:
            aid = ad.get('id')
            if not aid or not self._alarm_def_is_active(ad):
                continue
            eid = f'evt-{aid}'
            if eid in seen:
                continue
            seen.add(eid)
            pid = ad.get('pointId')
            events.append({
                'id': eid,
                'alarmDefinitionId': aid,
                'deviceId': ad.get('deviceId'),
                'pointId': pid,
                'severity': ad.get('severity', 'warning'),
                'state': 'active',
                'message': self._alarm_message(ad),
                'triggeredAt': self._point_last_updated(pid),
            })
        return events

    def health_endpoint(self, env, data):
        return {
            'status': 'ok',
            'appTitle': self.app_title,
            'siteName': self.site_name,
            'routePrefix': self.route_prefix,
            'agentIdentity': self.core.identity,
            'lastPublishAt': self.last_publish_at,
            'defaultTrendPointId': getattr(self, '_default_trend_point_id', None),
            'counts': {
                'devices': len(self.devices),
                'points': len(self.point_meta),
                'activeAlarms': len(self._alarm_events())
            },
            'trendPolicy': {
                'intervalMinutes': self.trend_interval_minutes,
                'retentionDays': self.default_trend_retention_days,
                'maxSamplesPerPoint': self.max_trend_samples
            },
            'volttron': {
                'status': 'connected',
                'subscriptions': [f'devices/{d}/all' for d in self.bacnet_devices]
            }
        }

    def devices_endpoint(self, env, data):
        return {'items': [self._device_summary(d) for d in self.devices.values()]}

    def points_endpoint(self, env, data):
        params = self._query_params(env)
        device_filter = params.get('deviceId', [None])[0]
        items = [self._point_record(pid, m) for pid, m in self.point_meta.items()]
        if device_filter:
            items = [i for i in items if i['deviceId'] == device_filter]
        return {'items': items}

    def polling_endpoint(self, env, data):
        return {
            'devices': [
                {
                    'deviceId': d['id'],
                    'name': d['displayName'],
                    'pollingEnabled': d['pollingEnabled'],
                    'lastSeen': d['lastSeen']
                }
                for d in self.devices.values()
            ]
        }

    def alarm_definitions_endpoint(self, env, data):
        return {'items': deepcopy(self.alarm_definitions)}

    def alarm_events_endpoint(self, env, data):
        return {'items': self._alarm_events()}

    def trends_endpoint(self, env, data):
        params = self._query_params(env)
        default_pid = getattr(self, '_default_trend_point_id', None) or next(iter(self.point_meta))
        point_id = params.get('pointId', [default_pid])[0]
        if point_id not in self.trends:
            point_id = default_pid
        meta = self.point_meta.get(point_id, {})
        values = [s['value'] for s in self.trends.get(point_id, []) if isinstance(s.get('value'), (int, float))]
        latest = values[-1] if values else None
        minimum = min(values) if values else None
        maximum = max(values) if values else None
        average = round(sum(values) / len(values), 2) if values else None
        return {
            'pointId': point_id,
            'label': meta.get('label', point_id),
            'units': meta.get('units'),
            'retentionDays': self.default_trend_retention_days,
            'intervalMinutes': self.trend_interval_minutes,
            'items': list(self.trends.get(point_id, [])),
            'summary': {'latest': latest, 'min': minimum, 'max': maximum, 'avg': average}
        }

    def notification_logs_endpoint(self, env, data):
        return {'items': deepcopy(self.notification_logs)}

    def notifications_config_endpoint(self, env, data):
        return {
            'smtp': deepcopy(self.smtp_config),
            'emailNotificationSupported': True,
            'note': 'Bench placeholder; wire SMTP in agent config later.'
        }

    def setpoints_endpoint(self, env, data):
        params = self._query_params(env)
        device_filter = params.get('deviceId', [None])[0]
        items = [self._point_record(pid, m) for pid, m in self.point_meta.items() if m.get('adjustable')]
        if device_filter:
            items = [i for i in items if i['deviceId'] == device_filter]
        return {'items': items}

    def setpoint_write_endpoint(self, env, data):
        if not isinstance(data, dict):
            return {'status': 'error', 'message': 'JSON body required'}
        point_id = data.get('pointId')
        raw_value = data.get('value')
        if point_id not in self.point_meta:
            return {'status': 'error', 'message': f'Unknown pointId: {point_id}'}
        meta = self.point_meta[point_id]
        if not meta.get('adjustable'):
            return {'status': 'error', 'message': f'Point not adjustable: {point_id}'}
        device_id = meta['deviceId']
        point_name = meta['name']
        try:
            value = float(raw_value) if meta['kind'] == 'analog' else raw_value
            result = self.vip.rpc.call(PLATFORM_DRIVER_IDENTITY, 'set_point', device_id, point_name, value).get(timeout=15)
            now = utc_now_iso()
            self.notification_logs.append({
                'timestamp': now,
                'channel': 'write',
                'recipient': device_id,
                'eventId': point_id,
                'status': f'setpoint-write-ok:{value}',
                'error': None
            })
            self.notification_logs = self.notification_logs[-100:]
            return {'status': 'ok', 'pointId': point_id, 'deviceId': device_id, 'pointName': point_name, 'requestedValue': value, 'result': result, 'timestamp': now}
        except Exception as exc:
            _log.exception('Setpoint write failed %s', point_id)
            return {'status': 'error', 'pointId': point_id, 'message': str(exc)}

    def graphics_overview_endpoint(self, env, data):
        equipment_graphics = {}
        for pid, m in self.point_meta.items():
            gkey = m.get('graphicGroup') or 'default'
            grp = equipment_graphics.setdefault(gkey, {'groupKey': gkey, 'deviceIds': set(), 'points': []})
            rec = self._point_record(pid, m)
            grp['points'].append(rec)
            grp['deviceIds'].add(m['deviceId'])
        for gkey, grp in equipment_graphics.items():
            grp['deviceIds'] = sorted(grp['deviceIds'])
        return {
            'systemOverview': {
                'siteName': self.site_name,
                'equipment': [self._device_summary(d) for d in self.devices.values()]
            },
            'equipmentGraphics': equipment_graphics,
        }

    def system_metrics_endpoint(self, env, data):
        mem = _read_proc_mem()
        load = _read_proc_loadavg()
        disk = _disk_root()
        cpu = _cpu_percent_simple()
        return {
            'timestamp': utc_now_iso(),
            'cpuPercent': cpu,
            'loadavg': load,
            'memory': mem,
            'diskRoot': disk,
            'hostname': os.uname().nodename if hasattr(os, 'uname') else None,
        }

    def agents_vctl_endpoint(self, env, data):
        out, err, code = self._run_vctl(['list'])
        return {
            'exitCode': code,
            'stderr': err,
            'stdout': out,
            'agents': self._parse_vctl_agents(out),
            'vctlPath': self.vctl_path,
            'volttronRoot': self.volttron_root,
            'volttronHome': self._volttron_home,
        }

    def agents_lifecycle_endpoint(self, env, data):
        if not self.allow_agent_lifecycle:
            return {'status': 'error', 'message': 'Agent lifecycle API disabled in agent config'}
        if not isinstance(data, dict):
            return {'status': 'error', 'message': 'JSON body required'}
        action = (data.get('action') or '').lower()
        tag = data.get('tag')
        uuid = data.get('uuid')
        if action not in ('start', 'stop', 'restart', 'remove'):
            return {'status': 'error', 'message': 'action must be start|stop|restart|remove'}
        if action == 'remove':
            if uuid:
                args = ['remove', uuid]
            elif tag:
                args = ['remove', '--tag', str(tag)]
            else:
                return {'status': 'error', 'message': 'remove requires uuid or tag'}
        else:
            if not tag and not uuid:
                return {'status': 'error', 'message': 'tag or uuid required'}
            if tag:
                args = [action, '--tag', str(tag)]
            else:
                args = [action, str(uuid)]
        out, err, code = self._run_vctl(args)
        return {'status': 'ok' if code == 0 else 'error', 'exitCode': code, 'stdout': out, 'stderr': err, 'args': args}

    def driver_configs_list_endpoint(self, env, data):
        out, err, code = self._run_vctl(['config', 'list', PLATFORM_DRIVER_IDENTITY])
        names = []
        for line in (out or '').splitlines():
            line = line.strip()
            if not line or line.startswith('---'):
                continue
            names.append(line.split()[0] if line.split() else line)
        return {'exitCode': code, 'stderr': err, 'items': sorted(set(names))}

    def driver_config_get_endpoint(self, env, data):
        params = self._query_params(env)
        name = params.get('name', [None])[0]
        if not name:
            return {'status': 'error', 'message': 'name query parameter required'}
        out, err, code = self._run_vctl(['config', 'get', PLATFORM_DRIVER_IDENTITY, name])
        return {'name': name, 'exitCode': code, 'stderr': err, 'content': out}

    def driver_config_store_endpoint(self, env, data):
        if not self.allow_driver_config_writes:
            return {'status': 'error', 'message': 'Driver config writes disabled in agent config'}
        if not isinstance(data, dict):
            return {'status': 'error', 'message': 'JSON body required'}
        name = data.get('name')
        content = data.get('content')
        is_csv = bool(data.get('csv'))
        if not name or content is None:
            return {'status': 'error', 'message': 'name and content required'}
        suffix = '.csv' if is_csv else '.json'
        fd, path = tempfile.mkstemp(suffix=suffix, text=True)
        try:
            os.close(fd)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content if isinstance(content, str) else json.dumps(content, indent=2))
            args = ['config', 'store', PLATFORM_DRIVER_IDENTITY, name, path]
            if is_csv:
                args.append('--csv')
            out, err, code = self._run_vctl(args)
            return {'status': 'ok' if code == 0 else 'error', 'exitCode': code, 'stdout': out, 'stderr': err}
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    def driver_config_delete_endpoint(self, env, data):
        if not self.allow_driver_config_writes:
            return {'status': 'error', 'message': 'Driver config writes disabled in agent config'}
        if not isinstance(data, dict):
            return {'status': 'error', 'message': 'JSON body required'}
        name = data.get('name')
        if not name:
            return {'status': 'error', 'message': 'name required'}
        out, err, code = self._run_vctl(['config', 'delete', PLATFORM_DRIVER_IDENTITY, name])
        return {'status': 'ok' if code == 0 else 'error', 'exitCode': code, 'stdout': out, 'stderr': err}

    def schedule_endpoint(self, env, data):
        method = (env.get('REQUEST_METHOD') or 'GET').upper()
        if method == 'GET':
            return self._load_schedule()
        if method == 'POST':
            if not isinstance(data, dict):
                return {'status': 'error', 'message': 'JSON body required'}
            self._save_schedule(data)
            return {'status': 'ok'}
        return {'status': 'error', 'message': 'Method not allowed'}


def main(argv=sys.argv):
    utils.vip_main(app8_web_agent, version=__version__)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
