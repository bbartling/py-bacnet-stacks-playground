# Vibe Code App 7 — VOLTTRON-hosted BAS Lite web app (option 1)

**What this is:** a first-pass BAS/BMS Lite app where **VOLTTRON itself serves the operator UI**. The UI is a static web app served from a web-enabled agent, with lightweight JSON endpoints exposed from that same agent.

**What this folder is for:** one place so you (or another AI session) can **understand the shape**, **install the web agent**, and **try the "serve React/static from VOLTTRON first" approach** before deciding whether to split the frontend/backend later.

---

## Current intent

This is the explicit **option 1** experiment:

- custom operator-facing UI
- served by a VOLTTRON web-enabled agent
- lightweight backend/API shape
- VOLTTRON remains BACnet/middleware/runtime
- if this path gets nasty, move later to a separately hosted frontend/backend

This folder is **not** pretending to be the final polished product. It is the clean starting point for the "let VOLTTRON host the web app first" trial.

## Data / retention posture

For the current 2-device Pi bench, app 7 is intentionally biased toward **in-memory / bounded retention** to reduce Raspberry Pi SD-card wear.

Current posture:

- live dashboard state is served from the running agent process
- trend samples are currently held in bounded in-memory deques
- current config targets **5-minute trend handling** with a **31-day retention goal**
- this is a bench-friendly runtime cache shape, not a finished historian/database layer yet
- notification config/log state is lightweight and bench-oriented for now

This means yes: keeping high-churn dashboard/trend state in memory first is a valid anti-SD-wear strategy on this Pi-class bench.

---

## Frozen facts / working assumptions

| Item | Value |
|------|--------|
| Bench target | Raspberry Pi `bosspi` |
| SSH | `ben@192.168.204.12` |
| VOLTTRON repo | `/home/ben/volttron` |
| `VOLTTRON_HOME` | `/home/ben/.volttron` |
| venv | `source /home/ben/volttron/env/bin/activate` |
| App 7 agent source target on Pi | `/home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent` |
| UI route target | `/app7/` |
| JSON API example | `/app7/api/health` |

---

## What is in this folder

| Path | Purpose |
|------|---------|
| `docs/architecture.md` | architecture notes |
| `docs/backend-contract.md` | UI-facing API draft |
| `docs/alarm-model.md` | first-pass alarm/event model |
| `docs/hosting-options.md` | why option 1 is being tried first |
| `RECREATE.md` | installation / recreate notes |
| `volttron_data/ben_bacnet/app7_web_agent/` | actual VOLTTRON web-enabled agent scaffold |
| `archive/` | Pi checkpoint backup, config/log snapshots, and pause-status handoff |
| `src/` | earlier React/Vite shell used to define UI feel |

---

## Another AI session: do this first

1. SSH to `ben@192.168.204.12`
2. `cd /home/ben/volttron && export VOLTTRON_HOME=/home/ben/.volttron && source env/bin/activate`
3. `systemctl is-active volttron.service` and `vctl status`
4. copy `volttron_data/ben_bacnet/app7_web_agent` from this folder onto the Pi
5. install the agent with `enable_web=True` scaffold already in place
6. hit `/app7/` and `/app7/api/health`
7. only then judge whether the VOLTTRON-hosted path is clean enough to keep

---

## App 7, option 1 shape

### Operator UI

The app should feel like a slimmed-down Open-FDD-style interface, but intentionally simpler on this 2-device bench:

- sidebar with only theme toggle + equipment tree
- click a device in the tree and the main dashboard repopulates for that device
- point table / current values
- strong red alarm visibility
- trend view for the selected point
- minimal notification/trend/alarm notes instead of overbuilt config UI

For this bench phase, configuring alarms/trends through OpenClaw chat is acceptable and should be documented instead of forcing a heavy operator config surface too early.

Also document that another OpenClaw instance should be able to recreate this deployment, configure trends/alarms, assist the technician with SMTP dial-out testing during setup, and verify approved writable BACnet setpoints.

### API boundary

The frontend should still think in terms of a normal app API, even if the first pass is hosted from the same VOLTTRON agent.

That means the UI reads routes like:

- `/app7/api/health`
- `/app7/api/devices`
- `/app7/api/alarms/events`

### VOLTTRON role

VOLTTRON should keep doing the runtime-heavy work:

- BACnet Proxy
- Platform Driver
- scrape/publish
- supervisory logic
- shared/global coordination logic

The point of this option is **not** to turn VOLTTRON Central into the product UI. The point is to see whether a custom app can be hosted cleanly enough from a VOLTTRON web agent for MVP use.

---

## Files to care about inside the agent

| Path | Purpose |
|------|---------|
| `setup.py` | installable VOLTTRON package definition |
| `MANIFEST.in` | includes packaged static assets |
| `config` | route prefix / app metadata |
| `app7_web_agent/agent.py` | live API + BACnet/trend/setpoint logic |
| `app7_web_agent/__init__.py` | package marker |
| `app7_web_agent/webroot/app7/index.html` | operator UI shell served by VOLTTRON |
| `app7_web_agent/webroot/app7/app.js` | current browser-side UI logic |
| `app7_web_agent/webroot/app7/styles.css` | current app styling |

---

## Data / logging / Linux service notes

Current Pi posture should be documented and preserved:

- `volttron.service` is the main Linux service hosting the app platform
- app 7 runs as an agent under that service
- dashboard/trend state is currently in-memory and bounded to reduce SD-card wear
- file logging can be enabled/tuned when needed, but should stay deliberate
- advanced users may prefer `systemd-journald` retention/rotation controls for robust Linux service behavior

See also: `docs/tech-setup-cheatsheet.md`

## Daily commands

```bash
ssh ben@192.168.204.12
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate

vctl status
```

```bash
# Install / reinstall the app 7 web agent
vctl install --vip-identity ben.app7.web --tag ben-app7-web \
  /home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent \
  --config /home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent/config
```

```bash
vctl start --tag ben-app7-web
vctl status
```

```bash
# Check logs for the agent
grep -n -E 'app7|web|Traceback|ERROR|Exception' /home/ben/.volttron/volttron.log | tail -n 80
```

---

## Expected URLs once installed

Current live bench path on `bosspi`:

- `http://192.168.204.12:8080/app7/index.html`
- `http://192.168.204.12:8080/app7/api/health`
- `http://192.168.204.12:8080/app7/api/devices`
- `http://192.168.204.12:8080/app7/api/points`
- `http://192.168.204.12:8080/app7/api/trends?pointId=Zone1VAV::ZoneTemp`

The Pi web surface is currently coming from the proper systemd-managed VOLTTRON platform with `bind-web-address = http://192.168.204.12:8080` enabled.

---

## Decision rule for this option-1 trial

**Keep option 1** if:

- static assets serve cleanly
- route prefix handling is tolerable
- basic JSON endpoints are clean
- redeploy/update flow is not annoying

**Bail to option 2 later** if:

- path-prefix routing gets brittle
- auth/session behavior gets awkward
- frontend rebuild/redeploy becomes annoying
- app logic starts feeling forced into VOLTTRON just because it is there

---

## Relationship to app 6

`vibe_code_apps_6` is the proven VOLTTRON-on-Pi bench and custom-agent baseline.

`vibe_code_apps_7` is the next experiment: use that VOLTTRON base to host a small operator UI and app-shaped API, starting with the simplest integrated deployment path first.
