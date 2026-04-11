# 2026-04-11 app 7 pause status

## Goal of this run

Use `vibe_code_apps_6` as the Pi baseline and try **app 7 option 1** first:

- custom BAS Lite UI
- served directly from VOLTTRON
- lightweight UI/API shape
- real data from the 2 BACnet test bench devices

## What was completed

### Pi / platform

- confirmed `bosspi` baseline is healthy
- confirmed app 6 agents and BACnet path were the correct starting point
- confirmed the bench is using the proper `volttron.service` systemd-managed platform base on the Pi
- added `bind-web-address = http://192.168.204.12:8080` to `/home/ben/.volttron/config`
- installed missing VOLTTRON web dependencies with:

```bash
cd /home/ben/volttron
source env/bin/activate
python3 bootstrap.py --web
```

- restarted VOLTTRON successfully with web bind enabled
- confirmed port `8080` is listening on the Pi

### BACnet / driver proof

- reran BACnet proxy scan
- confirmed the 2 live bench devices:
  - `192.168.204.13` / device `3456789`
  - `192.168.204.14` / device `3456790`
- confirmed `platform.driver` resumed scraping and publishing live data
- confirmed GL36 agents still run on top of that data

### App 7 deploy

- copied `app7_web_agent` onto the Pi under:
  - `/home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent`
- installed agent:
  - identity `ben.app7.web`
  - tag `ben-app7-web`
- agent status reached `running` / `GOOD`

## What is working at pause

- VOLTTRON platform running
- web bind active on `http://192.168.204.12:8080`
- BACnet Proxy running
- Platform Driver running
- listener + GL36 agents running
- real BACnet values visible in logs
- app 7 agent installed and healthy from VOLTTRON’s perspective

## Current implementation posture

The old `/app7` route-registration blocker has been solved since this pause note was first written.

Current live posture now is:

- `/app7/index.html` is serving from the Pi
- `/app7/api/health`, `/app7/api/devices`, `/app7/api/points`, and trend/config endpoints are live
- dashboard is intentionally being simplified around theme toggle + equipment tree + one repopulated device dashboard
- trend view is moving toward Plotly-style zoom/pan/export behavior
- alarm/trend setup via OpenClaw chat is considered acceptable for this bench phase

## Follow-on simplification direction

After getting the shell/API working, the next UI direction is to simplify the dashboard:

- sidebar should contain only theme toggle + equipment tree
- clicking a device should repopulate a single simpler dashboard for that device
- avoid heavy config panels for this 2-device bench
- document that alarm/trend setup can be driven via OpenClaw chat for now
- trend view should move toward a Plotly-style chart with zoom/pan/export instead of a homemade sparkline

## Handy current commands

```bash
ssh ben@192.168.204.12
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate
vctl status
```

```bash
curl http://192.168.204.12:8080/
curl http://192.168.204.12:8080/app7/api/health
```

```bash
tail -n 120 /home/ben/volttron/volttron.log
```

## Current observed status at pause

- `ben.app7.web` = `GOOD`
- `platform.bacnet_proxy` = `GOOD`
- `platform.driver` = `GOOD`
- `listener.bacnet` = `GOOD`
- `gl36.vav.requests` = `GOOD`
- `gl36.ahu.trimrespond` = `GOOD`

The bench is in a good enough place to stop, breathe, and resume with the route fix next.
