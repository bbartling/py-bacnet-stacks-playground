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


class GL36AhuTrimRespondAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super().__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self.agentid = self.config.get('agentid', 'gl36_ahu_trim_respond_agent')
        self.ahu_topic = self.config.get('ahu_topic', 'devices/BensFakeAHU/all')
        self.vav_request_topic = self.config.get('vav_request_topic', 'gl36/vav/request_summary')
        self.publish_topic = self.config.get('publish_topic', 'gl36/ahu/recommendations')
        self.write_recommendations = bool(self.config.get('write_recommendations', False))
        self.platform_driver_identity = self.config.get('platform_driver_identity', 'platform.driver')
        self.static_pressure_point = self.config.get('static_pressure_setpoint_point', 'DAP_SP')
        self.sat_setpoint_point = self.config.get('sat_setpoint_point', 'SAT_SP')
        self.fan_status_point = self.config.get('fan_status_point', 'SF_S')
        self.fan_command_point = self.config.get('fan_command_point', 'SF_C')
        self.startup_delay_sec = int(self.config.get('startup_delay_sec', 30))
        self.update_interval_sec = int(self.config.get('update_interval_sec', 30))
        self.ignore_requests = int(self.config.get('ignore_requests', 0))
        self.static_pressure = self.config.get('static_pressure', {})
        self.supply_air_temperature = self.config.get('supply_air_temperature', {})
        self.last_ahu = None
        self.last_vav_summary = None
        self.start_time = None
        self.last_update = None
        self.last_recommendation = None
        level = getattr(logging, str(self.config.get('log_level', 'INFO')).upper(), logging.INFO)
        _log.setLevel(level)

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        self.start_time = datetime.utcnow()
        self.vip.pubsub.subscribe(peer='pubsub', prefix=self.ahu_topic, callback=self._ahu_callback).get(timeout=10)
        self.vip.pubsub.subscribe(peer='pubsub', prefix=self.vav_request_topic, callback=self._vav_callback).get(timeout=10)
        self.core.periodic(self.update_interval_sec, self.evaluate)
        self.vip.health.set_status(STATUS_GOOD, f'{self.agentid} subscribed to AHU + VAV summary topics')
        _log.info('GL36 AHU trim/respond agent started in recommendation mode=%s', not self.write_recommendations)

    def _ahu_callback(self, peer, sender, bus, topic, headers, message):
        self.last_ahu = message[0] if isinstance(message, list) and message else message

    def _vav_callback(self, peer, sender, bus, topic, headers, message):
        self.last_vav_summary = message

    def evaluate(self):
        if not isinstance(self.last_ahu, dict) or not isinstance(self.last_vav_summary, dict):
            return
        uptime = (datetime.utcnow() - self.start_time).total_seconds()
        if uptime < self.startup_delay_sec:
            _log.info('Startup delay active: %.1fs remaining', self.startup_delay_sec - uptime)
            return

        fan_running = bool(self.last_ahu.get(self.fan_status_point) or self.last_ahu.get(self.fan_command_point))
        current_static = self._num(self.last_ahu.get(self.static_pressure_point))
        current_sat = self._num(self.last_ahu.get(self.sat_setpoint_point))
        if current_static is None or current_sat is None:
            return

        pressure_requests = int(self.last_vav_summary.get('pressure_request_total', 0))
        cooling_requests = int(self.last_vav_summary.get('cooling_request_total', 0))

        static_rec = self._trim_respond(current_static, pressure_requests, self.static_pressure)
        sat_rec = self._trim_respond(current_sat, cooling_requests, self.supply_air_temperature)

        recommendation = {
            'timestamp': utils.format_timestamp(datetime.utcnow()),
            'fan_running': fan_running,
            'write_recommendations_enabled': self.write_recommendations,
            'pressure_request_total': pressure_requests,
            'cooling_request_total': cooling_requests,
            'pressure_request_votes': int(self.last_vav_summary.get('pressure_request_votes', 0)),
            'cooling_request_votes': int(self.last_vav_summary.get('cooling_request_votes', 0)),
            'current_static_pressure_sp': current_static,
            'recommended_static_pressure_sp': static_rec,
            'current_sat_sp': current_sat,
            'recommended_sat_sp': sat_rec,
            'static_pressure_point': self.static_pressure_point,
            'sat_setpoint_point': self.sat_setpoint_point,
            'mode': 'write' if self.write_recommendations else 'publish_only',
        }
        self.last_recommendation = recommendation
        hdrs = {headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON, headers_mod.DATE: recommendation['timestamp']}
        self.vip.pubsub.publish('pubsub', self.publish_topic, headers=hdrs, message=recommendation)

        if self.write_recommendations and fan_running:
            try:
                self.vip.rpc.call(self.platform_driver_identity, 'set_point', 'gl36_ahu_trim_respond', 'BensFakeAHU/' + self.static_pressure_point, static_rec).get(timeout=20)
                self.vip.rpc.call(self.platform_driver_identity, 'set_point', 'gl36_ahu_trim_respond', 'BensFakeAHU/' + self.sat_setpoint_point, sat_rec).get(timeout=20)
                recommendation['mode'] = 'write_attempted'
            except Exception as exc:
                _log.exception('Write attempt failed: %s', exc)

        _log.info('GL36 AHU recommendation: pressure_req=%s cooling_req=%s static %.3f->%.3f sat %.1f->%.1f mode=%s', pressure_requests, cooling_requests, current_static, static_rec, current_sat, sat_rec, recommendation['mode'])

    def _trim_respond(self, current_sp, total_requests, cfg):
        sp_min = float(cfg.get('min', current_sp))
        sp_max = float(cfg.get('max', current_sp))
        trim = float(cfg.get('trim', 0.0))
        respond = float(cfg.get('respond', 0.0))
        respond_max = float(cfg.get('respond_max', abs(respond)))
        ignored = self.ignore_requests
        if total_requests <= ignored:
            new_sp = current_sp + trim
        else:
            delta = min(respond_max, respond * (total_requests - ignored))
            new_sp = current_sp + delta
        return max(sp_min, min(sp_max, round(new_sp, 3)))

    @RPC.export
    def get_latest_recommendation(self):
        return self.last_recommendation or {}

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
        utils.vip_main(GL36AhuTrimRespondAgent, version=__version__)
    except Exception:
        _log.exception('unhandled exception in GL36AhuTrimRespondAgent')


if __name__ == '__main__':
    sys.exit(main())
