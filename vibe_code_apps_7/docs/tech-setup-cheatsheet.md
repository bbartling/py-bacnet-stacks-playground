# Tech setup cheatsheet - BMS Lite on VOLTTRON + OpenClaw

This file is for future OpenClaw sessions and real technicians commissioning a Pi-hosted BAS Lite bench.

## Goal

Use OpenClaw + VOLTTRON to stand up a lightweight BACnet BMS Lite instance that provides:

- device dashboard
- trends
- alarms
- SMTP dial-out test posture
- writable approved setpoints

## Current bench assumptions

- Pi host: `bosspi`
- platform service: `volttron.service`
- web bind: `http://192.168.204.12:8080`
- app path: `http://192.168.204.12:8080/app7/index.html`
- BACnet devices:
  - `BensFakeAHU` @ `192.168.204.13` / device `3456789`
  - `Zone1VAV` @ `192.168.204.14` / device `3456790`

## What OpenClaw should handle well

Another OpenClaw instance should be able to:

1. verify the Pi service base is healthy
2. verify BACnet Proxy + Platform Driver are healthy
3. copy/install/reinstall `app7_web_agent`
4. validate trends/alarms/endpoints
5. help configure alarm posture in notes/APIs
6. help configure SMTP dial-out and run a technician-guided test
7. verify approved writable BACnet setpoints

## Core commands

```bash
ssh ben@192.168.204.12
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate
systemctl status volttron.service --no-pager
vctl status
```

```bash
curl http://192.168.204.12:8080/app7/api/health
curl http://192.168.204.12:8080/app7/api/devices
curl "http://192.168.204.12:8080/app7/api/points?deviceId=Zone1VAV"
curl "http://192.168.204.12:8080/app7/api/setpoints?deviceId=Zone1VAV"
```

## Agent install/reinstall

```bash
vctl remove --tag ben-app7-web
vctl install --vip-identity ben.app7.web --tag ben-app7-web \
  /home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent \
  --config /home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent/config
vctl start --tag ben-app7-web
vctl status
```

## Safe writable-point verification

Only test approved adjustable points.

Known current adjustable examples:
- `BensFakeAHU::SAT_SP`
- `Zone1VAV::ZoneCoolingSpt`
- `Zone1VAV::VAVFlowSpt`

Example API write through app 7:

```bash
python3 - <<'PY'
import json, urllib.request
req = urllib.request.Request(
    'http://192.168.204.12:8080/app7/api/setpoints/write',
    data=json.dumps({'pointId': 'Zone1VAV::ZoneCoolingSpt', 'value': 73.0}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
print(urllib.request.urlopen(req, timeout=20).read().decode())
PY
```

## SMTP dial-out testing posture

Current app 7 SMTP config is placeholder/default only.

Commissioning expectation:
- technician provides SMTP host/port/from/to/test target
- OpenClaw updates notes/config posture
- OpenClaw helps run a safe test
- result is documented in notes/logs

## Data retention / logging posture

Current bench posture is intentionally SD-card-friendly:

- high-churn dashboard/trend state is held in memory
- trend buffers are bounded
- current target shape is 5-minute trend handling with a 31-day retention goal
- file persistence should be added deliberately, not accidentally by noisy debug writes

## Linux service posture

Preferred posture:
- `volttron.service` is the main long-running service
- app 7 runs as an agent inside that platform
- use bounded logging
- advanced users can prefer `systemd-journald` controls for retention/rotation
- VOLTTRON startup helpers may support rotating-log options, but journald/systemd controls are usually the clearer ops posture on Linux

## Quick log checks

```bash
tail -n 120 /home/ben/volttron/volttron.log
```

```bash
grep -n -E 'app7|Traceback|ERROR|Exception' /home/ben/volttron/volttron.log | tail -n 80
```

## What the UI should stay focused on

- theme toggle
- equipment tree
- one repopulated dashboard per selected device
- Plotly trend with zoom/export/full-screen option
- writable setpoints for approved points only
- keep heavy config workflows out of the dashboard until truly needed
