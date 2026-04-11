# Vibe Code App 7 — BAS Lite on VOLTTRON (bosspi)

**What this is:** a lightweight BAS/BMS Lite web app hosted by VOLTTRON on the Raspberry Pi bench. It serves a simple operator dashboard for two BACnet devices, shows live values/trends/alarms, and supports approved writable setpoints through Platform Driver.

**What this folder is for:** one place so a human or another OpenClaw session can understand the setup, redeploy it, debug it, and continue the work without rereading a long chat log.

---

## Quick links

- [Frozen facts](#frozen-facts)
- [What works today](#what-works-today)
- [One-line install + start](#one-line-install--start-run-this-once)
- [Future deploys](#future-deploys)
- [If install says identity already exists](#if-install-says-identity-already-exists)
- [OpenClaw / tech commissioning flow](#openclaw--tech-commissioning-flow)
- [Data retention / logging posture](#data-retention--logging-posture)
- [Files that actually matter](#files-that-actually-matter)
- [What not to do](#what-not-to-do)

---

## Frozen facts

| Item | Value |
|------|--------|
| Pi host | `bosspi` |
| SSH | `ben@192.168.204.12` |
| VOLTTRON repo | `/home/ben/volttron` |
| `VOLTTRON_HOME` | `/home/ben/.volttron` |
| Service | `volttron.service` |
| App 7 path on Pi | `/home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent` |
| Live UI URL | `http://192.168.204.12:8080/app7/index.html` |
| Agent identity | `ben.app7.web` |
| Agent tag | `ben-app7-web` |

### Bench BACnet devices

| Name | BACnet IP | device_id |
|------|-----------|-----------|
| `BensFakeAHU` | `192.168.204.13` | `3456789` |
| `Zone1VAV` | `192.168.204.14` | `3456790` |

---

## What works today

- VOLTTRON web-hosted BAS Lite UI on the Pi
- simple operator dashboard
- theme toggle
- equipment tree
- live point table
- Plotly trend view
- bottom setpoint write dock
- live BACnet-fed values through `platform.driver`
- real writable setpoint path through Platform Driver
- app agent runs under the proper `volttron.service` systemd-managed platform

### Current tested healthy agents

- `ben.app7.web`
- `platform.driver`
- `platform.bacnet_proxy`
- `listener.bacnet`
- GL36 bench agents

---

## One-line install + start (run this once)

This was validated during the current workstream.

```powershell
ssh ben@192.168.204.12 "cd /home/ben/volttron && export VOLTTRON_HOME=/home/ben/.volttron && source env/bin/activate && vctl install --vip-identity ben.app7.web --tag ben-app7-web /home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent --config /home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent/config && vctl start --tag ben-app7-web && sleep 3 && vctl status"
```

You should see a row for:

- `ben.app7.web`
- `ben-app7-web`
- `running`
- `GOOD`

---

## Future deploys

If you only changed front-end files, copy the changed files and restart the agent.

### Minimal file copy pattern

```powershell
scp "C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_7\volttron_data\ben_bacnet\app7_web_agent\app7_web_agent\webroot\app7\app.js" ben@192.168.204.12:/home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/webroot/app7/app.js
```

```powershell
scp "C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_7\volttron_data\ben_bacnet\app7_web_agent\app7_web_agent\webroot\app7\styles.css" ben@192.168.204.12:/home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/webroot/app7/styles.css
```

```powershell
scp "C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_7\volttron_data\ben_bacnet\app7_web_agent\app7_web_agent\webroot\app7\index.html" ben@192.168.204.12:/home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/webroot/app7/index.html
```

### Restart the app 7 agent

This restart command was validated.

```powershell
ssh ben@192.168.204.12 "cd /home/ben/volttron && export VOLTTRON_HOME=/home/ben/.volttron && source env/bin/activate && vctl restart --tag ben-app7-web && sleep 2 && vctl status"
```

### Or use the repo script

This PowerShell script was validated and now works:

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_7
.\deploy-app7-to-bosspi.ps1
```

Behavior:

- copies the whole `app7_web_agent` folder to the Pi
- if the agent already exists → restarts it
- if the agent is missing → installs + starts it

---

## If install says identity already exists

First inspect what is there:

```powershell
ssh ben@192.168.204.12 "cd /home/ben/volttron && export VOLTTRON_HOME=/home/ben/.volttron && source env/bin/activate && vctl list && vctl status"
```

If App 7 already exists and you need to remove the old one explicitly:

```powershell
ssh ben@192.168.204.12 "cd /home/ben/volttron && export VOLTTRON_HOME=/home/ben/.volttron && source env/bin/activate && vctl remove <UUID-HERE> && vctl install --vip-identity ben.app7.web --tag ben-app7-web /home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent --config /home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent/config && vctl start --tag ben-app7-web"
```

Replace `<UUID-HERE>` with the real UUID from `vctl list`.

---

## OpenClaw / tech commissioning flow

This folder should be enough context for another OpenClaw instance or a technician-assisted setup.

### OpenClaw should be able to help with

- deploying/redeploying the app on the Pi
- validating BACnet Proxy + Platform Driver health
- checking the live UI/API path
- verifying writable setpoints on approved points
- setting up trend/alarm posture through chat + notes
- helping test SMTP dial-out during commissioning

### Human-readable expectation

This app is **not** trying to be a giant full BAS front-end yet.

The intended bench UX is:

- simple device tree
- one selected-device dashboard
- point table
- current alarms
- trend view
- bottom setpoint writer

And then use OpenClaw chat for:

- high limits
- low limits
- alarm enable/disable
- retention tweaks
- SMTP testing/dial-out verification

That is cleaner than overbuilding forms for a 2-device bench.

---

## Data retention / logging posture

Current app 7 posture is intentionally Raspberry Pi / SD-card friendly.

### Current storage idea

- live dashboard state is served by the running agent
- trend data is bounded and memory-first
- current target shape is:
  - 5-minute trend handling
  - 31-day retention goal
- this is **not** a finished historian/database layer yet

### Why

To reduce SD-card wear.

### Practical guidance

- keep high-churn trend/UI state in memory first
- avoid chatty per-sample file writes unless really needed
- file logging should be deliberate
- advanced users may prefer journald/systemd retention controls for Linux service hygiene
- VOLTTRON startup/log rotation options may still be useful, but journald/systemd is often the clearer ops story on Linux

---

## Linux service / bench commands

### Check service + agents

```bash
ssh ben@192.168.204.12
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate

systemctl status volttron.service --no-pager
vctl status
```

### Restart whole VOLTTRON service if needed

```powershell
ssh ben@192.168.204.12 "sudo systemctl restart volttron.service && sleep 8 && systemctl status volttron.service --no-pager"
```

Then:

```powershell
ssh ben@192.168.204.12 "cd /home/ben/volttron && export VOLTTRON_HOME=/home/ben/.volttron && source env/bin/activate && vctl status"
```

### Check logs

```powershell
ssh ben@192.168.204.12 "tail -n 80 /home/ben/volttron/volttron.log"
```

```powershell
ssh ben@192.168.204.12 "grep -n -E 'app7|Traceback|ERROR|Exception' /home/ben/volttron/volttron.log | tail -n 80"
```

---

## Files that actually matter

### Core app code

- `volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/agent.py`
- `volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/webroot/app7/index.html`
- `volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/webroot/app7/app.js`
- `volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/webroot/app7/styles.css`

### Important docs

- `RECREATE.md`
- `docs/tech-setup-cheatsheet.md`
- `docs/model-context-notes.md`
- `docs/backend-contract.md`
- `docs/architecture.md`

### Historical snapshots

- `archive/`
- `archive/backups/`

Snapshots are useful, but they are not the main source-of-truth code.

---

## What not to do

- do **not** hammer the VOLTTRON web service with overlapping endpoint calls on every click
- do **not** trust a redeploy without checking the actual installed Pi file if behavior looks unchanged
- do **not** assume browser cache is innocent — hard refresh matters
- do **not** leave stale prototype code as if it were current source-of-truth
- do **not** let background refresh stomp form input while a human is typing
- do **not** overbuild config UI for this 2-device bench when OpenClaw chat is the cleaner tool

---

## See also

- `RECREATE.md`
- `docs/tech-setup-cheatsheet.md`
- `docs/model-context-notes.md`
