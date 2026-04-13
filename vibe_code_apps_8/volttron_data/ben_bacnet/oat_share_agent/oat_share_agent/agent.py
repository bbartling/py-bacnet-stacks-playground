"""
Supervisory share agent (test bench): read one analog from a source BACnet driver
instance, then write the same value to one or more target points.

Typical BAS pattern: OAT wired at a boiler / utility panel, networked to AHUs / VAVs.

Default cadence: 900 s (15 minutes) — one BACnet read (via Platform Driver get_point)
and one write per target (set_point) each cycle.

Platform Driver RPC path for get_point must match the config-store device key **without**
the leading ``devices/`` segment (e.g. key ``devices/campus/bench/ahu1`` → path
``campus/bench/ahu1``). set_point uses the driver **topic name** / device id (often the
last segment or the name you see in ``devices/<name>/all`` — here ``BensFakeAHU``).
"""

import logging
import sys
from datetime import datetime

import gevent

from volttron.platform.agent import utils
from volttron.platform.messaging.health import STATUS_GOOD, STATUS_BAD
from volttron.platform.vip.agent import Agent, Core

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1.0'


def oat_share_agent(config_path, **kwargs):
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}
    return OatShareAgent(config=config, **kwargs)


class OatShareAgent(Agent):
    """Periodic read / multi-write supervisory helper for shared sensors (e.g. OAT)."""

    def __init__(self, config=None, **kwargs):
        super(OatShareAgent, self).__init__(**kwargs)
        self.config = config or {}
        self.agentid = self.config.get('agentid', 'ben_oat_share')
        self.driver_identity = self.config.get('platform_driver_identity', 'platform.driver')
        self.interval_seconds = int(self.config.get('interval_seconds', 900))
        self.first_sync_delay_seconds = int(self.config.get('first_sync_delay_seconds', 30))
        self.source_device_path = str(self.config.get('source_device_path', 'BensFakeAHU')).strip()
        self.source_point = str(self.config.get('source_point', 'OA_T')).strip()
        raw_targets = self.config.get('targets') or []
        self.targets = []
        for row in raw_targets:
            if not isinstance(row, dict):
                continue
            did = row.get('device_id') or row.get('deviceId')
            pn = row.get('point_name') or row.get('pointName')
            if did and pn:
                self.targets.append({'device_id': str(did).strip(), 'point_name': str(pn).strip()})

        self._last_value = None
        self._last_sync_at = None
        self._last_error = None

        level = getattr(logging, str(self.config.get('log_level', 'INFO')).upper(), logging.INFO)
        _log.setLevel(level)

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        _log.info(
            '%s starting: every %ss read path=%r point=%r -> %d target(s)',
            self.agentid,
            self.interval_seconds,
            self.source_device_path,
            self.source_point,
            len(self.targets),
        )
        if not self.targets:
            _log.warning(
                '%s: no targets configured — only logs reads; add targets[] in config to write shared values.',
                self.agentid,
            )

        delay = max(0, self.first_sync_delay_seconds)
        gevent.spawn_later(delay, self._run_sync_safe)
        self.core.periodic(self.interval_seconds, self._run_sync_safe)
        self.vip.health.set_status(STATUS_GOOD, f'{self.agentid} periodic {self.interval_seconds}s')
        _log.info('%s scheduled first sync in %ss, then every %ss', self.agentid, delay, self.interval_seconds)

    def _run_sync_safe(self):
        try:
            self._sync_once()
        except Exception as exc:
            self._last_error = str(exc)
            _log.exception('%s sync failed: %s', self.agentid, exc)
            try:
                self.vip.health.set_status(STATUS_BAD, str(exc)[:240])
            except Exception:
                pass

    def _driver_get_point(self):
        """Return live value from source device via Platform Driver."""
        try:
            return self.vip.rpc.call(
                self.driver_identity,
                'get_point',
                path=self.source_device_path,
                point_name=self.source_point,
            ).get(timeout=45)
        except TypeError:
            return self.vip.rpc.call(
                self.driver_identity,
                'get_point',
                self.source_device_path,
                self.source_point,
            ).get(timeout=45)

    def _driver_set_point(self, device_id, point_name, value):
        return self.vip.rpc.call(
            self.driver_identity,
            'set_point',
            device_id,
            point_name,
            value,
        ).get(timeout=45)

    def _sync_once(self):
        now = datetime.utcnow()
        value = self._driver_get_point()
        self._last_value = value
        self._last_sync_at = now.isoformat() + 'Z'
        self._last_error = None
        _log.info('%s read %s::%s = %r', self.agentid, self.source_device_path, self.source_point, value)

        if not self.targets:
            self.vip.health.set_status(STATUS_GOOD, f'read ok, no targets; value={value!r}')
            return

        for t in self.targets:
            did, pn = t['device_id'], t['point_name']
            try:
                result = self._driver_set_point(did, pn, value)
                _log.info('%s wrote %s::%s <= %r (result=%r)', self.agentid, did, pn, value, result)
            except Exception as exc:
                self._last_error = f'{did}::{pn}: {exc}'
                _log.error('%s write failed %s::%s: %s', self.agentid, did, pn, exc)
                raise

        self.vip.health.set_status(
            STATUS_GOOD,
            f'ok value={value!r} targets={len(self.targets)}',
        )


def main(argv=sys.argv):
    utils.vip_main(oat_share_agent, version=__version__)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
