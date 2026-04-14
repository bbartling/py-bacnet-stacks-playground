import datetime as dt
import logging
import sys

import volttron.utils as utils
from volttron.client.vip.agent import Agent, Core

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = "0.2.0"
PLATFORM_DRIVER_IDENTITY = "platform.driver"


def oat_share_agent(config_path, **kwargs):
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}
    return OatShareAgent(config=config, **kwargs)


class OatShareAgent(Agent):
    def __init__(self, config=None, **kwargs):
        super(OatShareAgent, self).__init__(**kwargs)
        self.config = config or {}
        self.interval_seconds = int(self.config.get("interval_seconds", 900))
        self.first_sync_delay_seconds = int(self.config.get("first_sync_delay_seconds", 30))
        self.source_device_path = self.config.get("source_device_path", "BensFakeAHU")
        self.source_point = self.config.get("source_point", "OA_T")
        self.targets = list(self.config.get("targets") or [])

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        self.core.schedule(dt.datetime.utcnow() + dt.timedelta(seconds=self.first_sync_delay_seconds), self._sync_once)
        self.core.periodic(self.interval_seconds, self._sync_once)

    def _sync_once(self):
        try:
            value = self.vip.rpc.call(PLATFORM_DRIVER_IDENTITY, "get_point", self.source_device_path, self.source_point).get(timeout=20)
            for t in self.targets:
                did = t.get("device_id")
                p = t.get("point_name")
                if not did or not p:
                    continue
                try:
                    self.vip.rpc.call(PLATFORM_DRIVER_IDENTITY, "set_point", did, p, value).get(timeout=20)
                except Exception:
                    _log.exception("target write failed %s %s", did, p)
            _log.info("OAT share synced %s=%s to %d targets", self.source_point, value, len(self.targets))
        except Exception:
            _log.exception("oat share sync failed")


def main(argv=sys.argv):
    utils.vip_main(oat_share_agent, version=__version__)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
