import logging
import sys
from datetime import datetime

from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.messaging.health import STATUS_GOOD
from volttron.platform.vip.agent import Agent, Core, RPC

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1'


class GL36VavRequestAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super().__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self.agentid = self.config.get('agentid', 'gl36_vav_request_agent')
        self.publish_topic = self.config.get('publish_topic', 'gl36/vav/request_summary')
        self.publish_detail_topic = self.config.get('publish_detail_topic', 'gl36/vav/request_details')
        self.vavs = self.config.get('vavs', [])
        self.exec_period_sec = int(self.config.get('exec_period_sec', 10))
        self.press_persist_sec = int(self.config.get('press_persist_sec', 60))
        self.temp_persist_sec = int(self.config.get('temp_persist_sec', 120))
        self.temp_suppress_sec = int(self.config.get('temp_suppress_sec', 60))
        self.use_imperial = bool(self.config.get('use_imperial', True))
        self.state = {}
        level = getattr(logging, str(self.config.get('log_level', 'INFO')).upper(), logging.INFO)
        _log.setLevel(level)

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        for vav in self.vavs:
            self.state[vav['name']] = {
                'press_high_timer': 0,
                'press_med_timer': 0,
                'temp_high_timer': 0,
                'temp_med_timer': 0,
                'temp_suppress_timer': self.temp_suppress_sec,
                'last_pressure_req': 0,
                'last_cooling_req': 0,
                'last_payload': None,
                'last_result': None,
                'last_seen': None,
            }
            self.vip.pubsub.subscribe(peer='pubsub', prefix=vav['topic'], callback=self._make_callback(vav)).get(timeout=10)
            _log.info('Subscribed to %s for %s', vav['topic'], vav['name'])
        self.vip.health.set_status(STATUS_GOOD, f'{self.agentid} watching {len(self.vavs)} VAV topics')

    def _make_callback(self, vav):
        def _callback(peer, sender, bus, topic, headers, message):
            self.handle_vav_publish(vav, headers, message)
        return _callback

    def _to_values(self, message):
        if isinstance(message, list) and message:
            return message[0]
        return message

    def handle_vav_publish(self, vav, headers, message):
        values = self._to_values(message)
        if not isinstance(values, dict):
            _log.warning('Unexpected message for %s: %r', vav['name'], message)
            return
        st = self.state[vav['name']]
        st['last_payload'] = values
        st['last_seen'] = headers.get(headers_mod.TIMESTAMP) or headers.get('TimeStamp') or headers.get('Date') or utils.format_timestamp(datetime.utcnow())
        result = self.compute_requests(vav, st, values)
        st['last_result'] = result
        self.publish_summary()

    def compute_requests(self, vav, st, values):
        zt = self._num(values.get(vav.get('zone_temp_point', 'ZoneTemp')))
        zsp = self._num(values.get(vav.get('zone_cooling_setpoint_point', 'ZoneCoolingSpt')))
        zd = self._num(values.get(vav.get('zone_demand_point', 'ZoneDemand')))
        flow = self._num(values.get(vav.get('vav_flow_point', 'VAVFlow')))
        flow_sp = self._num(values.get(vav.get('vav_flow_setpoint_point', 'VAVFlowSpt')))
        damper = self._num(values.get(vav.get('vav_damper_cmd_point', 'VAVDamperCmd')))

        st['temp_suppress_timer'] = min(self.temp_suppress_sec, st['temp_suppress_timer'] + self.exec_period_sec)
        pressure_req = self._compute_pressure_request(st, flow, flow_sp, damper)
        cooling_req = self._compute_cooling_request(st, zt, zsp, zd)
        st['last_pressure_req'] = pressure_req
        st['last_cooling_req'] = cooling_req
        return {
            'vav_name': vav['name'],
            'timestamp': st['last_seen'],
            'pressure_requests': pressure_req,
            'cooling_requests': cooling_req,
            'zone_temp': zt,
            'zone_cooling_setpoint': zsp,
            'zone_demand': zd,
            'vav_flow': flow,
            'vav_flow_setpoint': flow_sp,
            'damper_cmd': damper,
        }

    def _compute_pressure_request(self, st, flow, flow_sp, damper):
        if flow is None or flow_sp is None or damper is None or flow_sp <= 0:
            st['press_high_timer'] = 0
            st['press_med_timer'] = 0
            return 0
        ratio = flow / flow_sp
        cond3 = ratio < 0.50 and damper >= 95.0
        cond2 = ratio < 0.70 and damper >= 95.0
        st['press_high_timer'] = st['press_high_timer'] + self.exec_period_sec if cond3 else 0
        st['press_med_timer'] = st['press_med_timer'] + self.exec_period_sec if cond2 else 0
        if st['press_high_timer'] >= self.press_persist_sec:
            return 3
        if st['press_med_timer'] >= self.press_persist_sec:
            return 2
        if damper >= 95.0:
            return 1
        if st['last_pressure_req'] == 1 and damper >= 85.0:
            return 1
        return 0

    def _compute_cooling_request(self, st, zone_temp, zone_sp, zone_demand):
        if zone_temp is None or zone_sp is None or zone_demand is None:
            st['temp_high_timer'] = 0
            st['temp_med_timer'] = 0
            return 0
        diff = zone_temp - zone_sp
        high_diff = 5.0 if self.use_imperial else 3.0
        med_diff = 3.0 if self.use_imperial else 2.0
        if st['temp_suppress_timer'] >= self.temp_suppress_sec:
            if diff >= high_diff:
                st['temp_high_timer'] += self.exec_period_sec
                st['temp_med_timer'] = 0
            elif diff >= med_diff:
                st['temp_med_timer'] += self.exec_period_sec
                st['temp_high_timer'] = 0
            else:
                st['temp_high_timer'] = 0
                st['temp_med_timer'] = 0
            if st['temp_high_timer'] >= self.temp_persist_sec:
                return 3
            if st['temp_med_timer'] >= self.temp_persist_sec:
                return 2
        else:
            st['temp_high_timer'] = 0
            st['temp_med_timer'] = 0
        if zone_demand > 95.0:
            return 1
        if st['last_cooling_req'] == 1 and zone_demand >= 85.0:
            return 1
        return 0

    def publish_summary(self):
        details = []
        pressure_total = 0
        cooling_total = 0
        active_vavs = 0
        for vav in self.vavs:
            result = self.state[vav['name']].get('last_result')
            if not result:
                continue
            active_vavs += 1
            pressure_total += int(result['pressure_requests'])
            cooling_total += int(result['cooling_requests'])
            details.append(result)
        summary = {
            'timestamp': utils.format_timestamp(datetime.utcnow()),
            'active_vav_count': active_vavs,
            'configured_vav_count': len(self.vavs),
            'pressure_request_total': pressure_total,
            'cooling_request_total': cooling_total,
            'pressure_request_votes': sum(1 for x in details if x['pressure_requests'] > 0),
            'cooling_request_votes': sum(1 for x in details if x['cooling_requests'] > 0),
            'details': details,
        }
        hdrs = {headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON, headers_mod.DATE: utils.format_timestamp(datetime.utcnow())}
        self.vip.pubsub.publish('pubsub', self.publish_topic, headers=hdrs, message=summary)
        self.vip.pubsub.publish('pubsub', self.publish_detail_topic, headers=hdrs, message=details)
        _log.info('GL36 VAV summary: active=%s pressure_total=%s cooling_total=%s', active_vavs, pressure_total, cooling_total)

    @RPC.export
    def get_summary(self):
        details = [self.state[v['name']].get('last_result') for v in self.vavs if self.state[v['name']].get('last_result')]
        return {
            'configured_vav_count': len(self.vavs),
            'active_vav_count': len(details),
            'pressure_request_total': sum(int(x['pressure_requests']) for x in details),
            'cooling_request_total': sum(int(x['cooling_requests']) for x in details),
            'details': details,
        }

    @staticmethod
    def _num(value):
        try:
            if value is None:
                return None
            return float(value)
        except Exception:
            return None


def main(argv=sys.argv):
    try:
        utils.vip_main(GL36VavRequestAgent, version=__version__)
    except Exception:
        _log.exception('unhandled exception in GL36VavRequestAgent')


if __name__ == '__main__':
    sys.exit(main())
