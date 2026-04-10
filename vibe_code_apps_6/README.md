# Vibe Code App 6 — VOLTTRON edge bench (bosspi)

**What this is:** VOLTTRON 9 on a Raspberry Pi ingests BACnet via Platform Driver + BACnet Proxy. Three small custom agents subscribe, log CSV, and run GL36-style supervisory logic (recommendations only by default).

**What this folder is for:** One place so you (or another AI session) can **verify the bench** or **recreate it** without rereading long handoff docs. Deep narrative and full agent source live in `archive/`.

---

## Frozen facts (change these if the bench moves)

| Item | Value |
|------|--------|
| SSH | `ben@192.168.204.12` (hostname `bosspi`) |
| VOLTTRON repo | `/home/ben/volttron` |
| `VOLTTRON_HOME` | `/home/ben/.volttron` |
| venv | `source /home/ben/volttron/env/bin/activate` |
| Bench data | `/home/ben/volttron/volttron_data/ben_bacnet` |
| CSV output | `.../ben_bacnet/csv_logs/` |

**Devices (Platform Driver):**

| Name | BACnet IP | device_id |
|------|-----------|-----------|
| BensFakeAHU | 192.168.204.13 | 3456789 |
| Zone1VAV | 192.168.204.14 | 3456790 |

**Agents (VIP identity → tag):**

| Identity | Tag | Role |
|----------|-----|------|
| `platform.bacnet_proxy` | `bacnet-proxy` | BACnet stack |
| `platform.driver` | `platform-driver` | scrapes devices |
| `listener.bacnet` | `listener-bacnet` | example listener |
| `ben.csv-logger` | `ben-csv-logger` | daily CSV from publishes + startup RPC demo |
| `gl36.vav.requests` | `gl36-vav-requests` | VAV request counts → pubsub |
| `gl36.ahu.trimrespond` | `gl36-ahu-trimrespond` | AHU SP/SAT **recommendations** (safe default) |

---

## Another AI session: do this first

1. SSH to `ben@192.168.204.12`
2. `cd /home/ben/volttron && export VOLTTRON_HOME=/home/ben/.volttron && source env/bin/activate`
3. `systemctl is-active volttron.service` and `vctl status`
4. `tail -n 80 /home/ben/.volttron/volttron.log`
5. If recreating from scratch, follow **`RECREATE.md`** in order — do not skip BACnet Proxy before Platform Driver config.

---

## Daily commands

```bash
ssh ben@192.168.204.12
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate

vctl status
tail -f /home/ben/.volttron/volttron.log
```

```bash
# Custom agents + errors (last lines)
grep -n -E 'ben_csv_logger|gl36_vav|gl36_ahu|Traceback|ERROR|Exception' /home/ben/.volttron/volttron.log | tail -n 80
```

```bash
ls -la /home/ben/volttron/volttron_data/ben_bacnet/csv_logs/
```

---

## Systemd (boot persistence)

Canonical unit file in this folder: **`volttron.service`** (copy to `/etc/systemd/system/volttron.service` on the Pi).

```ini
[Unit]
Description=VOLTTRON platform
After=network-online.target
Wants=network-online.target

[Service]
Type=forking
User=ben
Group=ben
WorkingDirectory=/home/ben/volttron
Environment=VOLTTRON_HOME=/home/ben/.volttron
PIDFile=/home/ben/.volttron/VOLTTRON_PID
ExecStart=/home/ben/volttron/start-volttron
ExecStop=/home/ben/volttron/stop-volttron
Restart=on-failure
RestartSec=10
TimeoutStartSec=90
TimeoutStopSec=60

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now volttron.service
```

---

## BACnet proxy config (minimal)

Path on Pi: `volttron_data/ben_bacnet/bacnet-proxy-config.json`

```json
{
  "device_address": "192.168.204.12/24",
  "max_apdu_length": 1024,
  "object_id": 299599,
  "object_name": "bosspi VOLTTRON BACnet proxy",
  "vendor_id": 15,
  "segmentation_supported": "segmentedBoth"
}
```

---

## Install custom agents (`vctl`)

Source on Pi (sync from `archive/` backups if missing):

- `.../ben_bacnet/demo_csv_logger_agent`
- `.../ben_bacnet/gl36_vav_request_agent`
- `.../ben_bacnet/gl36_ahu_trim_respond_agent`

```bash
vctl install --vip-identity ben.csv-logger --tag ben-csv-logger \
  /home/ben/volttron/volttron_data/ben_bacnet/demo_csv_logger_agent \
  --config /home/ben/volttron/volttron_data/ben_bacnet/demo_csv_logger_agent/config

vctl install --vip-identity gl36.vav.requests --tag gl36-vav-requests \
  /home/ben/volttron/volttron_data/ben_bacnet/gl36_vav_request_agent \
  --config /home/ben/volttron/volttron_data/ben_bacnet/gl36_vav_request_agent/config

vctl install --vip-identity gl36.ahu.trimrespond --tag gl36-ahu-trimrespond \
  /home/ben/volttron/volttron_data/ben_bacnet/gl36_ahu_trim_respond_agent \
  --config /home/ben/volttron/volttron_data/ben_bacnet/gl36_ahu_trim_respond_agent/config

vctl start --tag ben-csv-logger
vctl start --tag gl36-vav-requests
vctl start --tag gl36-ahu-trimrespond
```

Alternate dev install (CSV logger example):

```bash
python scripts/install-agent.py \
  -s /home/ben/volttron/volttron_data/ben_bacnet/demo_csv_logger_agent \
  -c /home/ben/volttron/volttron_data/ben_bacnet/demo_csv_logger_agent/config \
  -i ben.csv-logger \
  --tag ben-csv-logger \
  --start
```

---

## Agent code shape (VOLTTRON 9)

Every agent is a **Python package** + **`setup.py`** + **`config`** JSON. Pattern:

**`setup.py`** (standard VOLTTRON agent — finds package containing `agent.py`):

```python
from os import path
from setuptools import setup, find_packages

MAIN_MODULE = "agent"
packages = find_packages(".")
agent_package = ""
for package in packages:
    if path.isfile(package + "/" + MAIN_MODULE + ".py"):
        agent_package = package
        break
if not agent_package:
    raise RuntimeError("No agent package found")
agent_module = agent_package + "." + MAIN_MODULE
_temp = __import__(agent_module, globals(), locals(), ["__version__"], 0)
__version__ = _temp.__version__

setup(
    name=agent_package + "agent",
    version=__version__,
    install_requires=["volttron"],
    packages=packages,
    entry_points={"setuptools.installation": ["eggsecutable = " + agent_module + ":main"]},
)
```

**`your_pkg/agent.py`** (minimal skeleton):

```python
import logging
import sys
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = "0.1"


class MyAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super().__init__(**kwargs)
        self.config = utils.load_config(config_path)

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        _log.info("started")
        # self.vip.pubsub.subscribe(peer="pubsub", prefix="devices/Zone1VAV/all", callback=...)


def main(argv=sys.argv):
    utils.vip_main(MyAgent, version=__version__)


if __name__ == "__main__":
    sys.exit(main())
```

**CSV logger `config`** (example — topics + optional BACnet RPC demo on start):

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

Full production code for all three agents → **`archive/VOLTTRON-9-bosspi-agent-source-backup-2026-04-09.md`**.

---

## GL36 agents (one sentence each)

- **`gl36_vav_request_agent`:** Reads VAV publishes → cooling + static-pressure **request counts** → publishes `gl36/vav/request_summary` (and details).
- **`gl36_ahu_trim_respond_agent`:** Reads AHU publishes + VAV summary → **recommended** duct static and SAT setpoints; **publish/log only** unless you deliberately enable writes later.

Logic reference (Niagara-style notes): [bbartling/niagara4-vibe-code-addict — README_TRIM_RESPOND.md](https://github.com/bbartling/niagara4-vibe-code-addict/blob/develop/README_TRIM_RESPOND.md)

---

## Repo layout after cleanup

| Path | Purpose |
|------|---------|
| `README.md` | This file — ops + snippets |
| `RECREATE.md` | Step-by-step rebuild + Platform Driver JSON/CSVs |
| `volttron.service` | systemd unit |
| `archive/` | Old OpenClaw handoffs, Open-FDD notes, full runbook copy |

---

## Progression (rest of playground)

`vibe_code_apps_1` … `vibe_code_apps_5` → direct BAC0/BACpypes scripts. **App 6** → same ideas running **inside VOLTTRON** (always-on edge, pubsub, agents).
