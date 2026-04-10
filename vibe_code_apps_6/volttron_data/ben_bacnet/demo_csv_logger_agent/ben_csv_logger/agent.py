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
                self.vip.health.set_status(STATUS_BAD, f'RPC demo failed for {device["name"]}: {exc}')


def main(argv=sys.argv):
    try:
        utils.vip_main(BenCsvLoggerAgent, version=__version__)
    except Exception:
        _log.exception('unhandled exception in BenCsvLoggerAgent')


if __name__ == '__main__':
    sys.exit(main())
