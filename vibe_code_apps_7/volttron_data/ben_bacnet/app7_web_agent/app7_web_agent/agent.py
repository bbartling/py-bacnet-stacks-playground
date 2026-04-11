import collections
import datetime as dt
import json
import logging
import os
import sys
from copy import deepcopy

from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.2'


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
        self.max_trend_samples = int(self.config.get('max_trend_samples', 180))
        self.webroot = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'webroot'))

        self.devices = {
            'BensFakeAHU': {
                'id': 'BensFakeAHU',
                'name': 'BensFakeAHU',
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
        self.notification_logs = []
        self.last_publish_at = None

    def _build_point_meta(self):
        return {
            'BensFakeAHU::OA_T': {'pointId': 'BensFakeAHU::OA_T', 'deviceId': 'BensFakeAHU', 'name': 'OA_T', 'label': 'Outdoor Air Temp', 'units': '°F', 'kind': 'analog'},
            'BensFakeAHU::SA_T': {'pointId': 'BensFakeAHU::SA_T', 'deviceId': 'BensFakeAHU', 'name': 'SA_T', 'label': 'Supply Air Temp', 'units': '°F', 'kind': 'analog'},
            'BensFakeAHU::SAT_SP': {'pointId': 'BensFakeAHU::SAT_SP', 'deviceId': 'BensFakeAHU', 'name': 'SAT_SP', 'label': 'Supply Air Temp Setpoint', 'units': '°F', 'kind': 'analog'},
            'BensFakeAHU::DPR_O': {'pointId': 'BensFakeAHU::DPR_O', 'deviceId': 'BensFakeAHU', 'name': 'DPR_O', 'label': 'Damper Output', 'units': '%', 'kind': 'analog'},
            'BensFakeAHU::SF_S': {'pointId': 'BensFakeAHU::SF_S', 'deviceId': 'BensFakeAHU', 'name': 'SF_S', 'label': 'Supply Fan Status', 'units': 'bool', 'kind': 'binary'},
            'Zone1VAV::ZoneTemp': {'pointId': 'Zone1VAV::ZoneTemp', 'deviceId': 'Zone1VAV', 'name': 'ZoneTemp', 'label': 'Zone Temperature', 'units': '°F', 'kind': 'analog'},
            'Zone1VAV::ZoneCoolingSpt': {'pointId': 'Zone1VAV::ZoneCoolingSpt', 'deviceId': 'Zone1VAV', 'name': 'ZoneCoolingSpt', 'label': 'Zone Cooling Setpoint', 'units': '°F', 'kind': 'analog'},
            'Zone1VAV::VAVFlow': {'pointId': 'Zone1VAV::VAVFlow', 'deviceId': 'Zone1VAV', 'name': 'VAVFlow', 'label': 'Airflow', 'units': 'CFM', 'kind': 'analog'},
            'Zone1VAV::VAVFlowSpt': {'pointId': 'Zone1VAV::VAVFlowSpt', 'deviceId': 'Zone1VAV', 'name': 'VAVFlowSpt', 'label': 'Airflow Setpoint', 'units': 'CFM', 'kind': 'analog'},
            'Zone1VAV::VAVDamperCmd': {'pointId': 'Zone1VAV::VAVDamperCmd', 'deviceId': 'Zone1VAV', 'name': 'VAVDamperCmd', 'label': 'Damper Command', 'units': '%', 'kind': 'analog'},
            'Zone1VAV::ZoneDemand': {'pointId': 'Zone1VAV::ZoneDemand', 'deviceId': 'Zone1VAV', 'name': 'ZoneDemand', 'label': 'Zone Demand', 'units': '%', 'kind': 'analog'}
        }

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        _log.info('Starting app7 web agent with route prefix %s', self.route_prefix)
        self.vip.web.register_path(r'^' + self.route_prefix + r'/.*', self.webroot)
        self.vip.web.register_endpoint(self.route_prefix + '/api/health', self.health_endpoint)
        self.vip.web.register_endpoint(self.route_prefix + '/api/devices', self.devices_endpoint)
        self.vip.web.register_endpoint(self.route_prefix + '/api/points', self.points_endpoint)
        self.vip.web.register_endpoint(self.route_prefix + '/api/polling', self.polling_endpoint)
        self.vip.web.register_endpoint(self.route_prefix + '/api/alarms/definitions', self.alarm_definitions_endpoint)
        self.vip.web.register_endpoint(self.route_prefix + '/api/alarms/events', self.alarm_events_endpoint)
        self.vip.web.register_endpoint(self.route_prefix + '/api/trends', self.trends_endpoint)
        self.vip.web.register_endpoint(self.route_prefix + '/api/notifications/logs', self.notification_logs_endpoint)
        self.vip.pubsub.subscribe(peer='pubsub', prefix='devices/BensFakeAHU/all', callback=self._handle_publish)
        self.vip.pubsub.subscribe(peer='pubsub', prefix='devices/Zone1VAV/all', callback=self._handle_publish)
        _log.info('App7 web agent subscriptions registered for live BACnet driver data.')

    def _handle_publish(self, peer, sender, bus, topic, headers, message):
        try:
            payload = message[0] if isinstance(message, list) and message else message
            if not isinstance(payload, dict):
                return
            device_name = topic.split('/')[1]
            if device_name not in self.devices:
                return
            device = self.devices[device_name]
            timestamp = utc_now_iso()
            device['lastSeen'] = timestamp
            device['status'] = 'online'
            for point_name, value in payload.items():
                point_id = f'{device_name}::{point_name}'
                device['points'][point_name] = {
                    'value': value,
                    'lastUpdated': timestamp
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

    def _device_summary(self, device):
        status = device['status']
        if self._device_alarm_state(device) == 'alarm':
            status = 'alarm'
        return {
            'id': device['id'],
            'name': device['name'],
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
            'trendEnabled': point_id in self.trends
        }

    def _device_alarm_state(self, device):
        if device['id'] == 'Zone1VAV':
            zone_temp = self._safe_float(device['points'].get('ZoneTemp', {}).get('value'))
            zone_spt = self._safe_float(device['points'].get('ZoneCoolingSpt', {}).get('value'))
            if zone_temp is not None and zone_spt is not None and zone_temp > zone_spt + 1.0:
                return 'alarm'
        return 'normal'

    def _point_alarm_state(self, point_id):
        if point_id == 'Zone1VAV::ZoneTemp':
            zone_temp = self._safe_float(self.devices['Zone1VAV']['points'].get('ZoneTemp', {}).get('value'))
            zone_spt = self._safe_float(self.devices['Zone1VAV']['points'].get('ZoneCoolingSpt', {}).get('value'))
            if zone_temp is not None and zone_spt is not None and zone_temp > zone_spt + 1.0:
                return 'alarm'
        return 'normal'

    def _alarm_definitions(self):
        return [
            {
                'id': 'zone-temp-high',
                'name': 'Zone temperature high',
                'enabled': True,
                'deviceId': 'Zone1VAV',
                'pointId': 'Zone1VAV::ZoneTemp',
                'severity': 'warning',
                'conditionType': 'greaterThanSetpointPlusOffset',
                'condition': {'referencePointId': 'Zone1VAV::ZoneCoolingSpt', 'offset': 1.0},
                'messageTemplate': 'Zone1 VAV temperature high',
                'notifyChannels': ['smtp']
            }
        ]

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
                'message': f'Zone1 VAV temperature high: {zone_temp:.1f} °F vs setpoint {zone_spt:.1f} °F',
                'triggeredAt': self.devices['Zone1VAV']['points'].get('ZoneTemp', {}).get('lastUpdated') or utc_now_iso()
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
            'volttron': {
                'status': 'connected',
                'subscriptions': ['devices/BensFakeAHU/all', 'devices/Zone1VAV/all']
            }
        }

    def devices_endpoint(self, env, data):
        return {'items': [self._device_summary(device) for device in self.devices.values()]}

    def points_endpoint(self, env, data):
        items = [self._point_record(point_id, meta) for point_id, meta in self.point_meta.items()]
        return {'items': items}

    def polling_endpoint(self, env, data):
        return {
            'devices': [
                {
                    'deviceId': device['id'],
                    'name': device['name'],
                    'pollingEnabled': device['pollingEnabled'],
                    'lastSeen': device['lastSeen']
                }
                for device in self.devices.values()
            ]
        }

    def alarm_definitions_endpoint(self, env, data):
        return {'items': self._alarm_definitions()}

    def alarm_events_endpoint(self, env, data):
        return {'items': self._alarm_events()}

    def trends_endpoint(self, env, data):
        query = env.get('QUERY_STRING', '') if env else ''
        point_id = None
        for part in query.split('&'):
            if part.startswith('pointId='):
                point_id = part.split('=', 1)[1]
        if point_id and point_id in self.trends:
            return {'pointId': point_id, 'items': list(self.trends[point_id])}
        default_point = 'Zone1VAV::ZoneTemp'
        return {'pointId': default_point, 'items': list(self.trends.get(default_point, []))}

    def notification_logs_endpoint(self, env, data):
        return {'items': deepcopy(self.notification_logs)}


def main(argv=sys.argv):
    utils.vip_main(app7_web_agent, version=__version__)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
