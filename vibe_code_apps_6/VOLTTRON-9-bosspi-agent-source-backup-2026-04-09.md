# VOLTTRON 9 bosspi agent source backup

Created: 2026-04-09
Source host: `ben@192.168.204.12`
Primary code root on Pi: `/home/ben/volttron/volttron_data/ben_bacnet`

This is a durable human-readable backup of the actual custom agent source/config files currently on the Pi.

## Included agents

1. `demo_csv_logger_agent`
2. `gl36_vav_request_agent`
3. `gl36_ahu_trim_respond_agent`

---

## 1) demo_csv_logger_agent

Pi path: `/home/ben/volttron/volttron_data/ben_bacnet/demo_csv_logger_agent`

### setup.py
```python
from os import path
from setuptools import setup, find_packages

MAIN_MODULE = 'agent'
packages = find_packages('.')
agent_package = ''
for package in packages:
    if path.isfile(package + '/' + MAIN_MODULE + '.py'):
        agent_package = package
        break
if not agent_package:
    raise RuntimeError('No agent package found')
agent_module = agent_package + '.' + MAIN_MODULE
_temp = __import__(agent_module, globals(), locals(), ['__version__'], 0)
__version__ = _temp.__version__

setup(
    name=agent_package + 'agent',
    version=__version__,
    install_requires=['volttron'],
    packages=packages,
    entry_points={'setuptools.installation': ['eggsecutable = ' + agent_module + ':main']}
)
```

### config
```json
{
  "agentid": "ben_csv_logger",
  "csv_output_dir": "/home/ben/volttron/volttron_data/ben_bacnet/csv_logs",
  "devices": [
    {
      "name": "BensFakeAHU",
      "topic": "devices/BensFakeAHU/all",
      "address": "192.168.204.13",
      "proxy_identity": "platform.bacnet_proxy",
      "rpc_read_points": {
        "OA_T": ["analogInput", 6, "presentValue"],
        "SA_T": ["analogInput", 2, "presentValue"]
      }
    },
    {
      "name": "Zone1VAV",
      "topic": "devices/Zone1VAV/all",
      "address": "192.168.204.14",
      "proxy_identity": "platform.bacnet_proxy",
      "rpc_read_points": {
        "ZoneTemp": ["analogInput", 1, "presentValue"],
        "VAVFlow": ["analogInput", 2, "presentValue"]
      }
    }
  ],
  "rpc_demo_onstart": true,
  "log_level": "INFO"
}
```

### ben_csv_logger/__init__.py
```python
__version__ = '0.1'
```

### ben_csv_logger/agent.py
```python
import csv
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from volttron.platform.agent import utils
from volttron.platform.messaging.health import STATUS_GOOD, STATUS_BAD
from volttron.platform.vip.agent import Agent, Core

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1'


class BenCsvLoggerAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super().__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self.agentid = self.config.get('agentid', 'ben_csv_logger')
        self.csv_output_dir = Path(self.config.get('csv_output_dir', '/tmp/volttron_csv_logs'))
        self.devices = self.config.get('devices', [])
        self.rpc_demo_onstart = bool(self.config.get('rpc_demo_onstart', True))
        log_level = getattr(logging, str(self.config.get('log_level', 'INFO')).upper(), logging.INFO)
        _log.setLevel(log_level)
        self._subscribed = []

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        self.csv_output_dir.mkdir(parents=True, exist_ok=True)
        for device in self.devices:
            topic = device['topic']
            self.vip.pubsub.subscribe(peer='pubsub', prefix=topic, callback=self._make_callback(device)).get(timeout=10)
            self._subscribed.append(topic)
            _log.info('Subscribed to %s for %s', topic, device['name'])

        if self.rpc_demo_onstart:
            self.core.spawn(self._run_rpc_demo)

        self.vip.health.set_status(STATUS_GOOD, f'{self.agentid} subscribed to {len(self._subscribed)} topics')
        _log.info('CSV output directory: %s', self.csv_output_dir)

    def _make_callback(self, device):
        def _callback(peer, sender, bus, topic, headers, message):
            self.handle_device_publish(device, headers, message)
        return _callback

    def handle_device_publish(self, device, headers, message):
        timestamp = headers.get('TimeStamp') or headers.get('Date') or utils.format_timestamp(datetime.utcnow())
        values = message[0] if isinstance(message, list) and message else message
        meta = message[1] if isinstance(message, list) and len(message) > 1 and isinstance(message[1], dict) else {}
        if not isinstance(values, dict):
            _log.warning('Unexpected payload for %s: %r', device['name'], message)
            return
        self._append_csv(device['name'], timestamp, values, meta)
        _log.info('Logged %s fields for %s at %s', len(values), device['name'], timestamp)

    def _append_csv(self, device_name, timestamp, values, meta):
        datestr = timestamp[:10]
        path = self.csv_output_dir / f'{device_name}_{datestr}.csv'
        fieldnames = ['timestamp', 'device'] + sorted(values.keys())
        write_header = not path.exists() or path.stat().st_size == 0
        row = {'timestamp': timestamp, 'device': device_name}
        row.update(values)
        with path.open('a', newline='') as fp:
            writer = csv.DictWriter(fp, fieldnames=fieldnames, extrasaction='ignore')
            if write_header:
                writer.writeheader()
            writer.writerow(row)
        meta_path = self.csv_output_dir / f'{device_name}_{datestr}.meta.csv'
        if meta:
            meta_write_header = not meta_path.exists() or meta_path.stat().st_size == 0
            meta_row = {'timestamp': timestamp, 'device': device_name}
            for key, item in meta.items():
                if isinstance(item, dict):
                    meta_row[f'{key}__units'] = item.get('units', '')
                    meta_row[f'{key}__type'] = item.get('type', '')
            with meta_path.open('a', newline='') as fp:
                meta_writer = csv.DictWriter(fp, fieldnames=sorted(meta_row.keys()), extrasaction='ignore')
                if meta_write_header:
                    meta_writer.writeheader()
                meta_writer.writerow(meta_row)

    def _run_rpc_demo(self):
        for device in self.devices:
            point_map = device.get('rpc_read_points') or {}
            if not point_map:
                continue
            try:
                result = self.vip.rpc.call(
                    device.get('proxy_identity', 'platform.bacnet_proxy'),
                    'read_properties',
                    device['address'],
                    point_map
                ).get(timeout=20)
                _log.info('BACnet proxy RPC demo for %s at %s -> %r', device['name'], device['address'], result)
            except Exception as exc:
                _log.exception('BACnet proxy RPC demo failed for %s: %s', device['name'], exc)
                self.vip.health.set_status(STATUS_BAD, f'RPC demo failed for {device[name]}: {exc}')


def main(argv=sys.argv):
    try:
        utils.vip_main(BenCsvLoggerAgent, version=__version__)
    except Exception:
        _log.exception('unhandled exception in BenCsvLoggerAgent')


if __name__ == '__main__':
    sys.exit(main())
```

---

## 2) gl36_vav_request_agent

Pi path: `/home/ben/volttron/volttron_data/ben_bacnet/gl36_vav_request_agent`

### setup.py
```python
from os import path
from setuptools import setup, find_packages

MAIN_MODULE = 'agent'
packages = find_packages('.')
agent_package = ''
for package in packages:
    if path.isfile(package + '/' + MAIN_MODULE + '.py'):
        agent_package = package
        break
if not agent_package:
    raise RuntimeError('No agent package found')
agent_module = agent_package + '.' + MAIN_MODULE
_temp = __import__(agent_module, globals(), locals(), ['__version__'], 0)
__version__ = _temp.__version__

setup(
    name=agent_package + 'agent',
    version=__version__,
    install_requires=['volttron'],
    packages=packages,
    entry_points={'setuptools.installation': ['eggsecutable = ' + agent_module + ':main']}
)
```

### config
```json
{
  "agentid": "gl36_vav_request_agent",
  "publish_topic": "gl36/vav/request_summary",
  "publish_detail_topic": "gl36/vav/request_details",
  "exec_period_sec": 10,
  "press_persist_sec": 60,
  "temp_persist_sec": 120,
  "temp_suppress_sec": 60,
  "use_imperial": true,
  "log_level": "INFO",
  "vavs": [
    {
      "name": "Zone1VAV",
      "topic": "devices/Zone1VAV/all",
      "zone_temp_point": "ZoneTemp",
      "zone_cooling_setpoint_point": "ZoneCoolingSpt",
      "zone_demand_point": "ZoneDemand",
      "vav_flow_point": "VAVFlow",
      "vav_flow_setpoint_point": "VAVFlowSpt",
      "vav_damper_cmd_point": "VAVDamperCmd"
    }
  ]
}
```

### gl36_vav_request/__init__.py
```python
# GL36 VAV request agent package
```

### gl36_vav_request/agent.py
```python
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
```

---

## 3) gl36_ahu_trim_respond_agent

Pi path: `/home/ben/volttron/volttron_data/ben_bacnet/gl36_ahu_trim_respond_agent`

### setup.py
```python
from os import path
from setuptools import setup, find_packages

MAIN_MODULE = 'agent'
packages = find_packages('.')
agent_package = ''
for package in packages:
    if path.isfile(package + '/' + MAIN_MODULE + '.py'):
        agent_package = package
        break
if not agent_package:
    raise RuntimeError('No agent package found')
agent_module = agent_package + '.' + MAIN_MODULE
_temp = __import__(agent_module, globals(), locals(), ['__version__'], 0)
__version__ = _temp.__version__

setup(
    name=agent_package + 'agent',
    version=__version__,
    install_requires=['volttron'],
    packages=packages,
    entry_points={'setuptools.installation': ['eggsecutable = ' + agent_module + ':main']}
)
```

### config
```json
{
  "agentid": "gl36_ahu_trim_respond_agent",
  "ahu_topic": "devices/BensFakeAHU/all",
  "vav_request_topic": "gl36/vav/request_summary",
  "publish_topic": "gl36/ahu/recommendations",
  "platform_driver_identity": "platform.driver",
  "static_pressure_setpoint_point": "DAP_SP",
  "sat_setpoint_point": "SAT_SP",
  "fan_status_point": "SF_S",
  "fan_command_point": "SF_C",
  "write_recommendations": false,
  "startup_delay_sec": 30,
  "update_interval_sec": 30,
  "ignore_requests": 0,
  "log_level": "INFO",
  "static_pressure": {
    "min": 0.5,
    "max": 1.5,
    "trim": -0.04,
    "respond": 0.06,
    "respond_max": 0.15
  },
  "supply_air_temperature": {
    "min": 52.0,
    "max": 62.0,
    "trim": 0.5,
    "respond": -1.0,
    "respond_max": 3.0
  }
}
```

### gl36_ahu_trim_respond/__init__.py
```python
# GL36 AHU trim respond agent package
```

### gl36_ahu_trim_respond/agent.py
```python
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
```
