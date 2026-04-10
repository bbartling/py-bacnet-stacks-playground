# VOLTTRON 9.x bosspi demo-agent handoff

_Last updated: 2026-04-09_

## Executive summary

A new demo VOLTTRON 9 agent was created on Raspberry Pi host `ben@192.168.204.12` and installed into the running local ZMQ platform.

It does three useful things:

1. subscribes to Platform Driver publish topics for the two learned BACnet devices
2. logs those publish payloads to rotating daily CSV files on the Pi
3. demonstrates direct BACnet proxy RPC reads at agent startup using the live `platform.bacnet_proxy`

This was done against the actual installed platform version on the Pi:

- VOLTTRON repo: `/home/ben/volttron`
- git describe: `9.0.4-2-gd7db28185`
- `VOLTTRON_HOME=/home/ben/.volttron`
- message bus in current use: local ZMQ

## Known live bench context

### Host access

- SSH: `ssh ben@192.168.204.12`
- Hostname observed: `bosspi`
- Python observed on host shell: `Python 3.13.5`
- VOLTTRON virtualenv used by platform: `/home/ben/volttron/env`

### Existing running agents before demo work

Observed via `vctl status`:

- `platform.bacnet_proxy` tagged `bacnet-proxy`
- `platform.driver` tagged `platform-driver`
- `listener.bacnet` tagged `listener-bacnet`

### Learned BACnet devices already in Platform Driver

- `BensFakeAHU` at `192.168.204.13`, device id `3456789`
- `Zone1VAV` at `192.168.204.14`, device id `3456790`

### Existing Ben-facing setup notes already on Pi

- `/home/ben/volttron/volttron_data/ben_bacnet/README-ben-bosspi-volttron-bacnet.md`

## What was added

### New agent source on the Pi

Agent project root:

- `/home/ben/volttron/volttron_data/ben_bacnet/demo_csv_logger_agent`

Files created there:

- `/home/ben/volttron/volttron_data/ben_bacnet/demo_csv_logger_agent/setup.py`
- `/home/ben/volttron/volttron_data/ben_bacnet/demo_csv_logger_agent/config`
- `/home/ben/volttron/volttron_data/ben_bacnet/demo_csv_logger_agent/ben_csv_logger/__init__.py`
- `/home/ben/volttron/volttron_data/ben_bacnet/demo_csv_logger_agent/ben_csv_logger/agent.py`

### CSV output directory on the Pi

- `/home/ben/volttron/volttron_data/ben_bacnet/csv_logs`

Observed files after startup:

- `/home/ben/volttron/volttron_data/ben_bacnet/csv_logs/BensFakeAHU_2026-04-09.csv`
- `/home/ben/volttron/volttron_data/ben_bacnet/csv_logs/BensFakeAHU_2026-04-09.meta.csv`
- `/home/ben/volttron/volttron_data/ben_bacnet/csv_logs/Zone1VAV_2026-04-09.csv`
- `/home/ben/volttron/volttron_data/ben_bacnet/csv_logs/Zone1VAV_2026-04-09.meta.csv`

### Installed/running demo agent

Current installed agent identity/tag:

- VIP identity: `ben.csv-logger`
- tag: `ben-csv-logger`

Observed running install instance:

- UUID: `cc380569-a8e6-4c76-83e5-0cb56d8c536d`

## What actually worked

### Install/start flow used

From the Pi:

```bash
ssh ben@192.168.204.12
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate

python scripts/install-agent.py \
  -s /home/ben/volttron/volttron_data/ben_bacnet/demo_csv_logger_agent \
  -c /home/ben/volttron/volttron_data/ben_bacnet/demo_csv_logger_agent/config \
  -i ben.csv-logger \
  --tag ben-csv-logger \
  --start
```

This aligns with the VOLTTRON 9 repo docs under:

- `docs/source/developing-volttron/developing-agents/agent-development.rst`
- `docs/source/platform-features/control/agent-management-control.rst`

## VOLTTRON 9.x development pattern vs old 5.x expectations

### Practical difference

Do **not** assume the old “wizard-first” mental model from older tutorials.

What was actually confirmed in this VOLTTRON 9.0.4 repo:

- agents are still normal Python packages with a `setup.py`
- agent code still commonly uses `utils.vip_main(...)`
- `vctl install` exists for wheel/package install management
- `scripts/install-agent.py` is still a real and documented development workflow
- examples in the repo still use package directories like `examples/ListenerAgent`
- agent lifecycle/decorator patterns are the modern repo truth here: `@Core.receiver('onstart')`, pubsub subscription, RPC calls, packaging via `setup.py`

### Good current mental model

For this Pi’s VOLTTRON 9 setup, the reliable path is:

1. create a small Python package with `setup.py`
2. implement agent logic in `<package>/agent.py`
3. keep config in a separate config file
4. install via `scripts/install-agent.py` or package + `vctl install`
5. manage runtime with `vctl status`, `vctl start`, `vctl stop`, `vctl remove`, log tailing

### Model-routing-policy mindset for future OpenClaw work

Use the simplest path that matches the actual job:

- **Read live publishes first** when you want current device values already normalized by Platform Driver.
- **Use BACnet proxy RPC** when you need direct point reads or proof of object/property addressing.
- **Use config-store / driver configs** when you need durable truth about topics, point mappings, or registry-to-device wiring.
- **Use repo docs/source over memory** when there is any version doubt.
- **Treat old 5.x wizard assumptions as suspect** unless the current 9.x repo on the host confirms them.

In other words: route to the most grounded source of truth first.

## How the demo CSV agent works

### Subscriptions

The agent subscribes to these Platform Driver publish topics:

- `devices/BensFakeAHU/all`
- `devices/Zone1VAV/all`

### CSV behavior

For each incoming publish:

- it extracts the timestamp from VOLTTRON headers
- writes a row to a device/day CSV file
- writes metadata rows to a parallel `.meta.csv` file
- daily rotation is filename-based: `DeviceName_YYYY-MM-DD.csv`

### Startup BACnet RPC demo

On startup, it also performs a small direct BACnet proxy `read_properties` RPC for each device.

Configured successful demo reads:

- `BensFakeAHU`
  - `OA_T -> ["analogInput", 6, "presentValue"]`
  - `SA_T -> ["analogInput", 2, "presentValue"]`
- `Zone1VAV`
  - `ZoneTemp -> ["analogInput", 1, "presentValue"]`
  - `VAVFlow -> ["analogInput", 2, "presentValue"]`

Those object/instance/property tuples were derived from the live registry CSVs, not guessed from stale docs.

## Verification evidence

### Running agents

Observed `vctl status` included:

- `ben_csv_loggeragent-0.1  ben.csv-logger  ben-csv-logger  running`

### Platform log evidence

Observed successful startup RPC demo lines in `/home/ben/.volttron/volttron.log`:

```text
BACnet proxy RPC demo for BensFakeAHU at 192.168.204.13 -> {'SA_T': 63.83502197265625, 'OA_T': 77.96037292480469}
BACnet proxy RPC demo for Zone1VAV at 192.168.204.14 -> {'VAVFlow': 390.75360107421875, 'ZoneTemp': 73.73396301269531}
```

Observed ongoing CSV logging lines:

```text
Logged 17 fields for BensFakeAHU at 2026-04-09T19:11:20.206500+00:00
Logged 6 fields for Zone1VAV at 2026-04-09T19:11:20.657091+00:00
```

### Sample CSV contents

`BensFakeAHU_2026-04-09.csv`

```csv
timestamp,device,CLG_O,DAP_P,DAP_SP,DPR_O,ELEC_PWR,HTG_O,MA_T,OAT_NETWORK,OA_T,Occ_Schedule,RA_T,SAT_SP,SA_FLOW,SA_T,SF_C,SF_O,SF_S
2026-04-09T19:08:50.207025+00:00,BensFakeAHU,0.0,0.8981585502624512,1.0,0.0,154.8033447265625,0.0,71.60204315185547,60.0,34.10536193847656,1,65.96041870117188,55.0,11177.703125,56.00495910644531,0,72.5,1
```

`Zone1VAV_2026-04-09.csv`

```csv
timestamp,device,VAVDamperCmd,VAVFlow,VAVFlowSpt,ZoneCoolingSpt,ZoneDemand,ZoneTemp
2026-04-09T19:08:50.659620+00:00,Zone1VAV,50.0,395.30072021484375,800.0,72.0,61.647762298583984,70.78561401367188
```

## Useful exact paths

### Repo/docs/source references used

- `/home/ben/volttron/docs/source/developing-volttron/developing-agents/agent-development.rst`
- `/home/ben/volttron/docs/source/platform-features/control/agent-management-control.rst`
- `/home/ben/volttron/examples/ListenerAgent/listener/agent.py`
- `/home/ben/volttron/services/core/BACnetProxy/bacnet_proxy/agent.py`
- `/home/ben/volttron/services/core/PlatformDriverAgent/platform_driver/interfaces/bacnet.py`

### Existing bench config references

- `/home/ben/volttron/volttron_data/ben_bacnet/devices/BensFakeAHU.json`
- `/home/ben/volttron/volttron_data/ben_bacnet/devices/Zone1VAV.json`
- `/home/ben/volttron/volttron_data/ben_bacnet/registry_configs/bensfakeahu.csv`
- `/home/ben/volttron/volttron_data/ben_bacnet/registry_configs/zone1vav.csv`

## How to inspect/restart it yourself

### SSH in

```bash
ssh ben@192.168.204.12
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate
```

### Check platform + agents

```bash
vctl status
vctl list
```

### Restart only the demo agent

```bash
vctl stop cc380569-a8e6-4c76-83e5-0cb56d8c536d
vctl start cc380569-a8e6-4c76-83e5-0cb56d8c536d
```

If UUID changes after reinstall, use `vctl status` / `vctl list` first.

### Watch logs

```bash
tail -f /home/ben/.volttron/volttron.log
```

Useful grep targets:

```bash
grep -n "ben_csv_loggeragent\|BACnet proxy RPC demo\|Logged " /home/ben/.volttron/volttron.log | tail -n 50
```

### Inspect CSV output

```bash
ls -lah /home/ben/volttron/volttron_data/ben_bacnet/csv_logs
sed -n '1,5p' /home/ben/volttron/volttron_data/ben_bacnet/csv_logs/BensFakeAHU_$(date +%F).csv
sed -n '1,5p' /home/ben/volttron/volttron_data/ben_bacnet/csv_logs/Zone1VAV_$(date +%F).csv
```

### Reinstall after source changes

```bash
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate

vctl remove cc380569-a8e6-4c76-83e5-0cb56d8c536d
python scripts/install-agent.py \
  -s /home/ben/volttron/volttron_data/ben_bacnet/demo_csv_logger_agent \
  -c /home/ben/volttron/volttron_data/ben_bacnet/demo_csv_logger_agent/config \
  -i ben.csv-logger \
  --tag ben-csv-logger \
  --start
```

## OpenClaw handoff notes

### If a future OpenClaw session picks this up

Start with these checks in order:

1. SSH to `ben@192.168.204.12`
2. confirm `cd /home/ben/volttron && source env/bin/activate`
3. run `vctl status`
4. confirm `ben-csv-logger`, `bacnet-proxy`, and `platform-driver` are running
5. inspect `/home/ben/.volttron/volttron.log`
6. inspect `/home/ben/volttron/volttron_data/ben_bacnet/csv_logs`
7. verify device publish traffic still exists for `devices/BensFakeAHU/all` and `devices/Zone1VAV/all`

### Routing policy for future troubleshooting

- If CSV files stop updating but Platform Driver publishes continue: inspect agent code/install/runtime first.
- If both listener and CSV agent stop seeing data: inspect Platform Driver and BACnet proxy next.
- If RPC demo fails but publishes still work: re-check direct BACnet object mappings in registry/device configs.
- If point names drift: treat registry CSVs and device JSON configs as source of truth.
- If docs conflict with host reality: trust the Pi’s current repo/docs/source and live behavior.

## Recommended next improvements

- expose a simple RPC method to force a one-shot snapshot write
- include topic name and sender columns in CSV
- write JSONL alongside CSV for schema-safe archiving
- add a small README in the agent directory itself
- optionally publish a derived “agent alive + last write timestamp” health topic
