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

## Current blocker

The app 7 agent is installed, but these still return `404 Not Found`:

- `/app7/`
- `/app7/api/health`
- `/app7/api/devices`
- `/app7/api/points`

So the remaining issue is now **web route registration / path shape**, not BACnet, not deployment, and not Pi reachability.

## Most likely next debugging direction

Compare `app7_web_agent/app7_web_agent/agent.py` against VOLTTRON’s `examples/SimpleWebAgent/simpleweb/agent.py` and adjust route registration to match what this platform expects.

Key suspicion:

- using regex-ish path registration was probably wrong for this platform version
- the next iteration should likely use the simpler registration style shown by `SimpleWebAgent`

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
