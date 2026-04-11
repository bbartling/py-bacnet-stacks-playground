import collections
import datetime as dt
import logging
import os
import sys
from copy import deepcopy
from urllib.parse import parse_qs

from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.3'
PLATFORM_DRIVER_IDENTITY = 'platform.driver'


def utc_now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')


def app7_web_agent(config_path, **kwargs):
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}
    return App7WebAgent(config=config, **kwargs)


class App7WebAgent(Agent):
    def __init__(self, config=None, **kwargs):
        super(App7WebAgent, self).__init__(enable_web=True, **kwargs)
        self.config = config or {}
        self.route_prefix = self.config.get('route_prefix', '/app7').rstrip('/')
        self.app_title = self.config.get('app_title', 'App 7 - BAS Lite')
        self.site_name = self.config.get('site_name', 'unknown-site')
        self.max_trend_samples = int(self.config.get('max_trend_samples', 9500))
        self.trend_interval_minutes = int(self.config.get('trend_interval_minutes', 5))
        self.default_trend_retention_days = int(self.config.get('default_trend_retention_days', 31))
        self.webroot = os.path.abspath(os.path.join(os.path.dirname(__file__), 'webroot'))

        self.devices = {
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
            }
        }
        self.point_meta = self._build_point_meta()
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
        self.alarm_definitions = [
            {
                'id': 'zone-temp-high',
                'name': 'Zone temperature high',
                'enabled': True,
                'deviceId': 'Zone1VAV',
                'pointId': 'Zone1VAV::ZoneTemp',
                'severity': 'warning',
                'conditionType': 'greaterThanSetpointPlusOffset',
                'condition': {'referencePointId': 'Zone1VAV::ZoneCoolingSpt', 'offset': 1.0},
                'messageTemplate': 'Zone 1 VAV temperature high',
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

    def _build_point_meta(self):
        return {
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
            'Zone1VAV::ZoneDemand': {'pointId': 'Zone1VAV::ZoneDemand', 'deviceId': 'Zone1VAV', 'name': 'ZoneDemand', 'label': 'Zone Demand', 'units': '%', 'kind': 'analog', 'adjustable': False, 'graphicGroup': 'vav'}
        }

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        _log.info('Starting app7 web agent with route prefix %s webroot=%s', self.route_prefix, self.webroot)
        self.vip.web.register_path(self.route_prefix, self.webroot)
        self.vip.web.register_endpoint(self.route_prefix + '/api/health', callback=self.health_endpoint)
        self.vip.web.register_endpoint(self.route_prefix + '/api/devices', callback=self.devices_endpoint)
        self.vip.web.register_endpoint(self.route_prefix + '/api/points', callback=self.points_endpoint)
        self.vip.web.register_endpoint(self.route_prefix + '/api/polling', callback=self.polling_endpoint)
        self.vip.web.register_endpoint(self.route_prefix + '/api/alarms/definitions', callback=self.alarm_definitions_endpoint)
        self.vip.web.register_endpoint(self.route_prefix + '/api/alarms/events', callback=self.alarm_events_endpoint)
        self.vip.web.register_endpoint(self.route_prefix + '/api/trends', callback=self.trends_endpoint)
        self.vip.web.register_endpoint(self.route_prefix + '/api/notifications/logs', callback=self.notification_logs_endpoint)
        self.vip.web.register_endpoint(self.route_prefix + '/api/graphics/overview', callback=self.graphics_overview_endpoint)
        self.vip.web.register_endpoint(self.route_prefix + '/api/notifications/config', callback=self.notifications_config_endpoint)
        self.vip.web.register_endpoint(self.route_prefix + '/api/setpoints', callback=self.setpoints_endpoint)
        self.vip.web.register_endpoint(self.route_prefix + '/api/setpoints/write', callback=self.setpoint_write_endpoint)
        self.vip.pubsub.subscribe(peer='pubsub', prefix='devices/BensFakeAHU/all', callback=self._handle_publish)
        self.vip.pubsub.subscribe(peer='pubsub', prefix='devices/Zone1VAV/all', callback=self._handle_publish)
        _log.info('App7 web agent subscriptions registered for live BACnet driver data.')

    def _handle_publish(self, peer, sender, bus, topic, headers, message):
        try:
            payload = message[0] if isinstance(message, list) and message else message
            meta_payload = message[1] if isinstance(message, list) and len(message) > 1 and isinstance(message[1], dict) else {}
            if not isinstance(payload, dict):
                return
            device_name = topic.split('/')[1]
            if device_name not in self.devices:
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
            _log.exception('Error processing publish for topic %s: %s', topic, exc)

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

    def _device_alarm_state(self, device):
        if device['id'] == 'Zone1VAV':
            zone_temp = self._safe_float(device['points'].get('ZoneTemp', {}).get('value'))
            zone_spt = self._safe_float(device['points'].get('ZoneCoolingSpt', {}).get('value'))
            if zone_temp is not None and zone_spt is not None and zone_temp > zone_spt + 1.0:
                return 'alarm'
        if device['id'] == 'BensFakeAHU':
            sf_s = device['points'].get('SF_S', {}).get('value')
            if sf_s in (0, False, '0', 'false', 'False'):
                return 'alarm'
        return 'normal'

    def _point_alarm_state(self, point_id):
        if point_id == 'Zone1VAV::ZoneTemp':
            zone_temp = self._safe_float(self.devices['Zone1VAV']['points'].get('ZoneTemp', {}).get('value'))
            zone_spt = self._safe_float(self.devices['Zone1VAV']['points'].get('ZoneCoolingSpt', {}).get('value'))
            if zone_temp is not None and zone_spt is not None and zone_temp > zone_spt + 1.0:
                return 'alarm'
        if point_id == 'BensFakeAHU::SF_S':
            sf_s = self.devices['BensFakeAHU']['points'].get('SF_S', {}).get('value')
            if sf_s in (0, False, '0', 'false', 'False'):
                return 'alarm'
        return 'normal'

    def _alarm_events(self):
        events = []
        zone_temp = self._safe_float(self.devices['Zone1VAV']['points'].get('ZoneTemp', {}).get('value'))
        zone_spt = self._safe_float(self.devices['Zone1VAV']['points'].get('ZoneCoolingSpt', {}).get('value'))
        if zone_temp is not None and zone_spt is not None and zone_temp > zone_spt + 1.0:
            events.append({
                'id': 'evt-zone-temp-high',
                'alarmDefinitionId': 'zone-temp-high',
                'deviceId': 'Zone1VAV',
                'pointId': 'Zone1VAV::ZoneTemp',
                'severity': 'warning',
                'state': 'active',
                'message': f'Zone 1 VAV temperature high: {zone_temp:.1f} °F vs setpoint {zone_spt:.1f} °F',
                'triggeredAt': self.devices['Zone1VAV']['points'].get('ZoneTemp', {}).get('lastUpdated') or utc_now_iso()
            })
        sf_s = self.devices['BensFakeAHU']['points'].get('SF_S', {}).get('value')
        if sf_s in (0, False, '0', 'false', 'False'):
            events.append({
                'id': 'evt-ahu-fan-status-failure',
                'alarmDefinitionId': 'ahu-fan-status-failure',
                'deviceId': 'BensFakeAHU',
                'pointId': 'BensFakeAHU::SF_S',
                'severity': 'critical',
                'state': 'active',
                'message': 'AHU supply fan status failure',
                'triggeredAt': self.devices['BensFakeAHU']['points'].get('SF_S', {}).get('lastUpdated') or utc_now_iso()
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
                'subscriptions': ['devices/BensFakeAHU/all', 'devices/Zone1VAV/all']
            }
        }

    def devices_endpoint(self, env, data):
        return {'items': [self._device_summary(device) for device in self.devices.values()]}

    def points_endpoint(self, env, data):
        params = self._query_params(env)
        device_filter = params.get('deviceId', [None])[0]
        items = [self._point_record(point_id, meta) for point_id, meta in self.point_meta.items()]
        if device_filter:
            items = [item for item in items if item['deviceId'] == device_filter]
        return {'items': items}

    def polling_endpoint(self, env, data):
        return {
            'devices': [
                {
                    'deviceId': device['id'],
                    'name': device['displayName'],
                    'pollingEnabled': device['pollingEnabled'],
                    'lastSeen': device['lastSeen']
                }
                for device in self.devices.values()
            ]
        }

    def alarm_definitions_endpoint(self, env, data):
        return {'items': deepcopy(self.alarm_definitions)}

    def alarm_events_endpoint(self, env, data):
        return {'items': self._alarm_events()}

    def trends_endpoint(self, env, data):
        params = self._query_params(env)
        point_id = params.get('pointId', ['Zone1VAV::ZoneTemp'])[0]
        if point_id not in self.trends:
            point_id = 'Zone1VAV::ZoneTemp'
        meta = self.point_meta.get(point_id, {})
        values = [sample['value'] for sample in self.trends.get(point_id, []) if isinstance(sample.get('value'), (int, float, float))]
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
            'summary': {
                'latest': latest,
                'min': minimum,
                'max': maximum,
                'avg': average
            }
        }

    def notification_logs_endpoint(self, env, data):
        return {'items': deepcopy(self.notification_logs)}

    def notifications_config_endpoint(self, env, data):
        return {
            'smtp': deepcopy(self.smtp_config),
            'emailNotificationSupported': True,
            'note': 'Bench placeholder config for future email alarming.'
        }

    def setpoints_endpoint(self, env, data):
        params = self._query_params(env)
        device_filter = params.get('deviceId', [None])[0]
        items = [self._point_record(point_id, meta) for point_id, meta in self.point_meta.items() if meta.get('adjustable')]
        if device_filter:
            items = [item for item in items if item['deviceId'] == device_filter]
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
            return {'status': 'error', 'message': f'Point is not marked adjustable: {point_id}'}
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
            return {
                'status': 'ok',
                'pointId': point_id,
                'deviceId': device_id,
                'pointName': point_name,
                'requestedValue': value,
                'result': result,
                'timestamp': now
            }
        except Exception as exc:
            _log.exception('Setpoint write failed for %s', point_id)
            return {
                'status': 'error',
                'pointId': point_id,
                'message': str(exc)
            }

    def graphics_overview_endpoint(self, env, data):
        return {
            'systemOverview': {
                'siteName': self.site_name,
                'equipment': [self._device_summary(device) for device in self.devices.values()]
            },
            'equipmentGraphics': {
                'ahu': {
                    'deviceId': 'BensFakeAHU',
                    'points': [self._point_record(pid, meta) for pid, meta in self.point_meta.items() if meta['deviceId'] == 'BensFakeAHU']
                },
                'vav': {
                    'deviceId': 'Zone1VAV',
                    'points': [self._point_record(pid, meta) for pid, meta in self.point_meta.items() if meta['deviceId'] == 'Zone1VAV']
                }
            }
        }


def main(argv=sys.argv):
    utils.vip_main(app7_web_agent, version=__version__)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
