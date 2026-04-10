# bosspi VOLTTRON — full recreate (configs + order)

Host: `ben@192.168.204.12`. Use **`/home/ben/volttron/env`** (not a random new venv).

**Order:** venv → start platform → BACnet Proxy → Platform Driver + config store → Listener → custom agents → systemd.

---

## 1) Shell

```bash
ssh ben@192.168.204.12
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate
```

If VOLTTRON not running:

```bash
volttron -vv -l "$VOLTTRON_HOME/volttron.log" &
sleep 5
```

---

## 2) BACnet Proxy

Config file: `volttron_data/ben_bacnet/bacnet-proxy-config.json` (see README for JSON).

```bash
vctl install --vip-identity platform.bacnet_proxy --tag bacnet-proxy \
  services/core/BACnetProxy \
  --config /home/ben/volttron/volttron_data/ben_bacnet/bacnet-proxy-config.json
```

---

## 3) Platform Driver — main `config`

Store as `platform.driver` / key `config` (JSON file e.g. `platform-driver-config.json`):

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

---

## 4) Platform Driver — devices + registries

**Device `devices/BensFakeAHU`:**

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

**Device `devices/Zone1VAV`:**

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

**`registry_configs/bensfakeahu.csv`:**

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

**`registry_configs/zone1vav.csv`:**

```csv
Reference Point Name,Volttron Point Name,Units,Unit Details,BACnet Object Type,Property,Writable,Index,Write Priority,Notes
ZoneTemp,ZoneTemp,degreesFahrenheit,,analogInput,presentValue,FALSE,1,,
VAVFlow,VAVFlow,cubicFeetPerMinute,,analogInput,presentValue,FALSE,2,,
ZoneCoolingSpt,ZoneCoolingSpt,degreesFahrenheit,,analogValue,presentValue,TRUE,1,8,
ZoneDemand,ZoneDemand,percent,,analogValue,presentValue,TRUE,2,8,
VAVFlowSpt,VAVFlowSpt,cubicFeetPerMinute,,analogValue,presentValue,TRUE,3,8,
VAVDamperCmd,VAVDamperCmd,percent,,analogOutput,presentValue,TRUE,1,8,
```

**Load config store:**

```bash
vctl install --vip-identity platform.driver --tag platform-driver \
  services/core/MasterDriverAgent

vctl config store platform.driver config /home/ben/volttron/volttron_data/ben_bacnet/platform-driver-config.json --json
vctl config store platform.driver registry_configs/bensfakeahu.csv /home/ben/volttron/volttron_data/ben_bacnet/registry_configs/bensfakeahu.csv --csv
vctl config store platform.driver registry_configs/zone1vav.csv /home/ben/volttron/volttron_data/ben_bacnet/registry_configs/zone1vav.csv --csv
vctl config store platform.driver devices/BensFakeAHU /home/ben/volttron/volttron_data/ben_bacnet/devices/BensFakeAHU.json --json
vctl config store platform.driver devices/Zone1VAV /home/ben/volttron/volttron_data/ben_bacnet/devices/Zone1VAV.json --json
```

(Adjust paths if your JSON files live next to the CSVs with those exact names.)

---

## 5) Listener

```bash
vctl install --vip-identity listener.bacnet --tag listener-bacnet examples/ListenerAgent
```

---

## 6) Start / enable core agents

```bash
vctl start --tag bacnet-proxy
vctl start --tag platform-driver
vctl start --tag listener-bacnet
vctl enable --tag bacnet-proxy
vctl enable --tag platform-driver
vctl enable --tag listener-bacnet
```

---

## 7) Custom agents

See **README.md** for `vctl install` lines. Agent trees must exist under `volttron_data/ben_bacnet/` (restore from `archive/VOLTTRON-9-bosspi-agent-source-backup-2026-04-09.md` if needed).

---

## 8) systemd

Install **`volttron.service`** from repo root to `/etc/systemd/system/`, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now volttron.service
```

---

## 9) Verify

```bash
vctl status
vctl config list platform.driver
grep -n -E 'Traceback|ERROR|Exception' /home/ben/.volttron/volttron.log | tail -n 40
```

---

## 10) Rebuild from scratch (human)

```bash
sudo systemctl stop volttron.service
tar -czf ~/volttron-pre-rebuild-$(date +%F-%H%M%S).tar.gz ~/.volttron ~/volttron/volttron_data/ben_bacnet /etc/systemd/system/volttron.service 2>/dev/null
```

Then repeat sections 1–8 in order.

---

## Pi notes

- **armv7l**, Raspbian 13 — native VOLTTRON preferred over Docker on this bench.
- **Python:** platform uses `/home/ben/volttron/env` (may differ from system `python3`).
