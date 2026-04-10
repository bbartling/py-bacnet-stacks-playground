# bosspi native VOLTTRON recreate runbook

_Date: 2026-04-10_
_Host: `ben@192.168.204.12` (`bosspi`)_

This is the clean recreate path for the current bench.

## Why native instead of Docker on this Pi

I checked the live host first.

Current hardware / OS snapshot:

- `armv7l`
- `Raspbian GNU/Linux 13 (trixie)`
- about `921 MiB` RAM total
- Docker was **not** installed

Because this is an older Pi-class host with limited RAM and the existing native VOLTTRON install was already healthy, the easiest and most reproducible path is:

- **native VOLTTRON on Python 3.10**
- **systemd service for boot persistence**
- **Platform Driver + BACnet Proxy + custom agents**

That is the path documented here.

## What was confirmed working

Using the live working environment at `/home/ben/volttron/env`, the following agents were healthy:

- `platform.bacnet_proxy`
- `platform.driver`
- `listener.bacnet`
- `ben.csv-logger`
- `gl36.vav.requests`
- `gl36.ahu.trimrespond`

## Backups made before further changes

Pi-local backup archive created:

- `/home/ben/volttron-native-backup-2026-04-10-090807.tar.gz`

Windows-side durable docs / code backups already live in this folder.

---

# 1) Human SSH access

From Windows PowerShell or a normal terminal:

```bash
ssh ben@192.168.204.12
```

## Useful first commands after login

```bash
hostname
pwd
whoami
```

Expected:

- hostname: `bosspi`
- home: `/home/ben`
- user: `ben`

---

# 2) Important live paths

- repo root: `/home/ben/volttron`
- runtime home: `/home/ben/.volttron`
- working native venv: `/home/ben/volttron/env`
- alternate scratch venv created later during troubleshooting: `/home/ben/volttron-venv`
- custom bench content: `/home/ben/volttron/volttron_data/ben_bacnet`

## Important note on venv choice

For the current healthy platform, use:

```bash
source /home/ben/volttron/env/bin/activate
```

That venv already has the older compatible `wheel.tool` path that current VOLTTRON expects.

---

# 3) Fast manual ops commands

```bash
ssh ben@192.168.204.12
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate
vctl status
vctl list
vctl peerlist
```

## Service status

```bash
systemctl status volttron.service
systemctl is-enabled volttron.service
systemctl is-active volttron.service
```

## Logs

```bash
tail -f /home/ben/.volttron/volttron.log
```

Focused grep:

```bash
grep -n -E 'ben_csv_loggeragent|gl36_vav_requestagent|gl36_ahu_trim_respondagent|BACnet proxy RPC demo|GL36 VAV summary|GL36 AHU recommendation|Traceback|ERROR|Exception' /home/ben/.volttron/volttron.log | tail -n 120
```

---

# 4) Exact current systemd unit

File:

- `/etc/systemd/system/volttron.service`

Current content:

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

Reload + enable if changed:

```bash
sudo systemctl daemon-reload
sudo systemctl enable volttron.service
sudo systemctl restart volttron.service
```

---

# 5) Exact current BACnet proxy config

Saved working file:

- `/home/ben/volttron/volttron_data/ben_bacnet/bacnet-proxy-config.json`

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

# 6) Exact current Platform Driver config store

## Main driver config

```json
{
  "driver_scrape_interval": 0.5,
  "publish_breadth_first_all": false,
  "publish_depth_first": false,
  "publish_breadth_first": false,
  "publish_depth_first_all": true,
  "group_offset_interval": 0.0
}
```

## Device: BensFakeAHU

Config store name:

- `devices/BensFakeAHU`

```json
{
  "driver_config": {
    "device_address": "192.168.204.13",
    "device_id": 3456789
  },
  "driver_type": "bacnet",
  "registry_config": "config://registry_configs/bensfakeahu.csv",
  "interval": 10,
  "timezone": "US/Central",
  "heart_beat_point": "",
  "group": 0
}
```

## Device: Zone1VAV

Config store name:

- `devices/Zone1VAV`

```json
{
  "driver_config": {
    "device_address": "192.168.204.14",
    "device_id": 3456790
  },
  "driver_type": "bacnet",
  "registry_config": "config://registry_configs/zone1vav.csv",
  "interval": 10,
  "timezone": "US/Central",
  "heart_beat_point": "",
  "group": 0
}
```

## Registry: BensFakeAHU

Config store name:

- `registry_configs/bensfakeahu.csv`

```csv
Reference Point Name,Volttron Point Name,Units,Unit Details,BACnet Object Type,Property,Writable,Index,Write Priority,Notes
DAP-P,DAP_P,inchesOfWater,,analogInput,presentValue,FALSE,1,,
SA-T,SA_T,degreesFahrenheit,,analogInput,presentValue,FALSE,2,,
MA-T,MA_T,degreesFahrenheit,,analogInput,presentValue,FALSE,3,,
RA-T,RA_T,degreesFahrenheit,,analogInput,presentValue,FALSE,4,,
SA-FLOW,SA_FLOW,cubicFeetPerMinute,,analogInput,presentValue,FALSE,5,,
OA-T,OA_T,degreesFahrenheit,,analogInput,presentValue,FALSE,6,,
ELEC-PWR,ELEC_PWR,kilowatts,,analogInput,presentValue,FALSE,7,,
SF-O,SF_O,percent,,analogOutput,presentValue,TRUE,1,8,Supply fan output
HTG-O,HTG_O,percent,,analogOutput,presentValue,TRUE,2,8,
CLG-O,CLG_O,percent,,analogOutput,presentValue,TRUE,3,8,
DPR-O,DPR_O,percent,,analogOutput,presentValue,TRUE,4,8,
DAP-SP,DAP_SP,inchesOfWater,,analogValue,presentValue,TRUE,1,8,
SAT-SP,SAT_SP,degreesFahrenheit,,analogValue,presentValue,TRUE,2,8,
OAT-NETWORK,OAT_NETWORK,degreesFahrenheit,,analogValue,presentValue,TRUE,3,8,
SF-S,SF_S,Boolean,,binaryInput,presentValue,FALSE,1,,Supply fan status
SF-C,SF_C,Boolean,,binaryOutput,presentValue,TRUE,1,8,Supply fan command
Occ-Schedule,Occ_Schedule,Enum,1=Occupied,multiStateValue,presentValue,TRUE,1,8,
```

## Registry: Zone1VAV

Config store name:

- `registry_configs/zone1vav.csv`

```csv
Reference Point Name,Volttron Point Name,Units,Unit Details,BACnet Object Type,Property,Writable,Index,Write Priority,Notes
ZoneTemp,ZoneTemp,degreesFahrenheit,,analogInput,presentValue,FALSE,1,,
VAVFlow,VAVFlow,cubicFeetPerMinute,,analogInput,presentValue,FALSE,2,,
ZoneCoolingSpt,ZoneCoolingSpt,degreesFahrenheit,,analogValue,presentValue,TRUE,1,8,
ZoneDemand,ZoneDemand,percent,,analogValue,presentValue,TRUE,2,8,
VAVFlowSpt,VAVFlowSpt,cubicFeetPerMinute,,analogValue,presentValue,TRUE,3,8,
VAVDamperCmd,VAVDamperCmd,percent,,analogOutput,presentValue,TRUE,1,8,
```

---

# 7) Core agents to install/reinstall

The current bench uses these built-in agents:

- `services/core/BACnetProxy`
- `services/core/MasterDriverAgent`
- `examples/ListenerAgent`

## Typical reinstall flow

```bash
ssh ben@192.168.204.12
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate
```

If VOLTTRON is not already running:

```bash
volttron -vv -l "$VOLTTRON_HOME/volttron.log" &
sleep 5
```

### BACnet Proxy

```bash
vctl install --vip-identity platform.bacnet_proxy --tag bacnet-proxy \
  services/core/BACnetProxy \
  --config /home/ben/volttron/volttron_data/ben_bacnet/bacnet-proxy-config.json
```

### Platform Driver

```bash
vctl install --vip-identity platform.driver --tag platform-driver \
  services/core/MasterDriverAgent
```

Load config store items:

```bash
vctl config store platform.driver config /home/ben/volttron/volttron_data/ben_bacnet/platform-driver-config.json --json
vctl config store platform.driver registry_configs/bensfakeahu.csv /home/ben/volttron/volttron_data/ben_bacnet/registry_configs/bensfakeahu.csv --csv
vctl config store platform.driver registry_configs/zone1vav.csv /home/ben/volttron/volttron_data/ben_bacnet/registry_configs/zone1vav.csv --csv
vctl config store platform.driver devices/BensFakeAHU /home/ben/volttron/volttron_data/ben_bacnet/devices/BensFakeAHU.json --json
vctl config store platform.driver devices/Zone1VAV /home/ben/volttron/volttron_data/ben_bacnet/devices/Zone1VAV.json --json
```

### Listener

```bash
vctl install --vip-identity listener.bacnet --tag listener-bacnet examples/ListenerAgent
```

Start and enable core agents:

```bash
vctl start --tag bacnet-proxy
vctl start --tag platform-driver
vctl start --tag listener-bacnet
vctl enable --tag bacnet-proxy
vctl enable --tag platform-driver
vctl enable --tag listener-bacnet
```

---

# 8) Custom agents to install/reinstall

Current source roots on the Pi:

- `/home/ben/volttron/volttron_data/ben_bacnet/demo_csv_logger_agent`
- `/home/ben/volttron/volttron_data/ben_bacnet/gl36_vav_request_agent`
- `/home/ben/volttron/volttron_data/ben_bacnet/gl36_ahu_trim_respond_agent`

## Demo CSV logger

```bash
vctl install --vip-identity ben.csv-logger --tag ben-csv-logger \
  /home/ben/volttron/volttron_data/ben_bacnet/demo_csv_logger_agent \
  --config /home/ben/volttron/volttron_data/ben_bacnet/demo_csv_logger_agent/config
```

## GL36 VAV request agent

```bash
vctl install --vip-identity gl36.vav.requests --tag gl36-vav-requests \
  /home/ben/volttron/volttron_data/ben_bacnet/gl36_vav_request_agent \
  --config /home/ben/volttron/volttron_data/ben_bacnet/gl36_vav_request_agent/config
```

## GL36 AHU trim/respond agent

```bash
vctl install --vip-identity gl36.ahu.trimrespond --tag gl36-ahu-trimrespond \
  /home/ben/volttron/volttron_data/ben_bacnet/gl36_ahu_trim_respond_agent \
  --config /home/ben/volttron/volttron_data/ben_bacnet/gl36_ahu_trim_respond_agent/config
```

Start and enable custom agents:

```bash
vctl start --tag ben-csv-logger
vctl start --tag gl36-vav-requests
vctl start --tag gl36-ahu-trimrespond

vctl enable --tag ben-csv-logger
vctl enable --tag gl36-vav-requests
vctl enable --tag gl36-ahu-trimrespond
```

---

# 9) Manual verification commands for a human

## Show all agents

```bash
vctl status
vctl list
vctl peerlist
```

## Show Platform Driver config store

```bash
vctl config list platform.driver
vctl config get platform.driver config
vctl config get platform.driver devices/BensFakeAHU
vctl config get platform.driver devices/Zone1VAV
```

## Check CSV output

```bash
ls -lah /home/ben/volttron/volttron_data/ben_bacnet/csv_logs
sed -n '1,5p' /home/ben/volttron/volttron_data/ben_bacnet/csv_logs/BensFakeAHU_$(date +%F).csv
sed -n '1,5p' /home/ben/volttron/volttron_data/ben_bacnet/csv_logs/Zone1VAV_$(date +%F).csv
```

## Watch logs live

```bash
tail -f /home/ben/.volttron/volttron.log
```

## Focus on custom agent behavior

```bash
grep -n -E 'Logged|GL36 VAV summary|GL36 AHU recommendation|BACnet proxy RPC demo|Traceback|ERROR|Exception' /home/ben/.volttron/volttron.log | tail -n 120
```

---

# 10) If a human wants to rebuild from scratch later

## Stop service

```bash
sudo systemctl stop volttron.service
```

## Keep backup first

```bash
tar -czf ~/volttron-pre-rebuild-$(date +%F-%H%M%S).tar.gz ~/.volttron ~/volttron/volttron_data/ben_bacnet /etc/systemd/system/volttron.service 2>/dev/null
```

## Then rebuild using this order

1. Activate `/home/ben/volttron/env`
2. Start VOLTTRON
3. Install BACnet Proxy
4. Install Platform Driver
5. Load config store items
6. Install Listener
7. Install custom agents
8. Enable all agents
9. Restart `volttron.service`
10. Verify with `vctl status`

---

# 11) Bottom line

For `bosspi`, native VOLTTRON is currently the right answer:

- it is already working
- it is lighter than a forced Docker migration on this hardware
- it is easier for a human to SSH in and recover manually
- the exact recreate commands are now documented here
