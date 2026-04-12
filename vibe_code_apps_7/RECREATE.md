# App 7 recreate notes — BAS Lite on VOLTTRON (bosspi)

This is the practical recreate / redeploy guide for app 7.

If you only need the short version, start with `README.md`.

---

## 1. Goal

Deploy a simple BAS Lite dashboard on the Pi bench where:

- VOLTTRON serves the UI
- BACnet data comes from the 2 bench devices through Platform Driver
- trends/alarms/setpoints are exposed in a lightweight app shell
- OpenClaw chat can assist with alarm/trend/SMTP commissioning work

---

## 2. Get onto the Pi and activate VOLTTRON

```bash
ssh ben@192.168.204.12
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate
```

---

## 3. Confirm base platform health

Use the proper Pi systemd-managed VOLTTRON base, not a random ad-hoc launch.

```bash
systemctl is-active volttron.service
systemctl status volttron.service --no-pager
vctl status
```

Expected bench posture:

- `volttron.service` is active
- `platform.driver` is `GOOD`
- `platform.bacnet_proxy` is `GOOD`
- `ben.app7.web` is `GOOD` once installed

---

## 4. Copy the app 7 source to the Pi

Source folder on Windows:

- `C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_7\volttron_data\ben_bacnet\app7_web_agent`

Target on Pi:

- `/home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent`

### Full copy

```powershell
scp -r "C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_7\volttron_data\ben_bacnet\app7_web_agent" ben@192.168.204.12:/home/ben/volttron/volttron_data/ben_bacnet/
```

### UI-only copy

```powershell
scp "C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_7\volttron_data\ben_bacnet\app7_web_agent\app7_web_agent\webroot\app7\app.js" ben@192.168.204.12:/home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/webroot/app7/app.js
```

```powershell
scp "C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_7\volttron_data\ben_bacnet\app7_web_agent\app7_web_agent\webroot\app7\styles.css" ben@192.168.204.12:/home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/webroot/app7/styles.css
```

```powershell
scp "C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_7\volttron_data\ben_bacnet\app7_web_agent\app7_web_agent\webroot\app7\index.html" ben@192.168.204.12:/home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/webroot/app7/index.html
```

---

## 5. Install + start (first time)

Validated command:

```powershell
ssh ben@192.168.204.12 "cd /home/ben/volttron && export VOLTTRON_HOME=/home/ben/.volttron && source env/bin/activate && vctl install --vip-identity ben.app7.web --tag ben-app7-web /home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent --config /home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent/config && vctl start --tag ben-app7-web && sleep 3 && vctl status"
```

---

## 6. Restart (most common future deploy)

Validated command:

```powershell
ssh ben@192.168.204.12 "cd /home/ben/volttron && export VOLTTRON_HOME=/home/ben/.volttron && source env/bin/activate && vctl restart --tag ben-app7-web && sleep 2 && vctl status"
```

---

## 7. Use the helper script

Validated helper script:

- `deploy-app7-to-bosspi.ps1`

Usage:

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_7
.\deploy-app7-to-bosspi.ps1
```

Behavior:

- copies `app7_web_agent` to the Pi
- if App 7 exists → restarts it
- if App 7 does not exist → installs + starts it

---

## 8. If install says identity already exists

Inspect:

```powershell
ssh ben@192.168.204.12 "cd /home/ben/volttron && export VOLTTRON_HOME=/home/ben/.volttron && source env/bin/activate && vctl list && vctl status"
```

Then remove the old UUID explicitly and reinstall:

```powershell
ssh ben@192.168.204.12 "cd /home/ben/volttron && export VOLTTRON_HOME=/home/ben/.volttron && source env/bin/activate && vctl remove <UUID-HERE> && vctl install --vip-identity ben.app7.web --tag ben-app7-web /home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent --config /home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent/config && vctl start --tag ben-app7-web"
```

---

## 9. Verify the app

### Browser

- `http://192.168.204.12:8080/app7/index.html`

### API examples

- `http://192.168.204.12:8080/app7/api/health`
- `http://192.168.204.12:8080/app7/api/devices`
- `http://192.168.204.12:8080/app7/api/points`

### Logs

```powershell
ssh ben@192.168.204.12 "grep -n -E 'app7|Traceback|ERROR|Exception' /home/ben/volttron/volttron.log | tail -n 80"
```

---

## 10. OpenClaw / tech commissioning posture

Another OpenClaw instance should be able to use this folder as context to:

- redeploy the app
- verify BACnet driver state
- verify approved writable setpoints
- help configure trends and alarms via chat + notes
- help configure/test SMTP dial-out with a technician present

For this bench, OpenClaw chat is a valid configuration surface for:

- high limits
- low limits
- alarm enable/disable
- retention changes
- SMTP testing

---

## 11. Data retention / logging posture

Current app 7 posture is intentionally Pi-friendly:

- high-churn dashboard/trend state is memory-first and bounded
- current target shape is 5-minute trend handling with a 31-day goal
- this is not yet a finished historian database
- file logging should be deliberate to avoid unnecessary SD-card wear
- advanced users may prefer journald/systemd retention controls for robust Linux service behavior

---

## 12. Big files that matter

- `volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/agent.py`
- `volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/webroot/app7/index.html`
- `volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/webroot/app7/app.js`
- `volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/webroot/app7/styles.css`

Also read:

- `docs/tech-setup-cheatsheet.md`
- `docs/model-context-notes.md`
- `docs/bosspi-volttron-dataflow-and-storage-tutorial.md`

---

## 13. Open-FDD VOLTTRON Central PoC integration notes (2026-04-12)

This bench was integrated to the active Open-FDD monorepo at:

- `https://github.com/bbartling/open-fdd`
- branch used during this PoC: `dev/work`

Central host used for this PoC:

- `192.168.204.16` (`hvac-edge-01`)
- user: `ben`
- Open-FDD repo path: `~/open-fdd`
- VOLTTRON Central runtime: `volttron1` via upstream `~/volttron-docker`

Edge host used for this PoC:

- `192.168.204.12` (`bosspi`)
- native VOLTTRON in `~/volttron`
- `VOLTTRON_HOME=/home/ben/.volttron`

### What was proven

- Open-FDD helper scripts on `.16` were enough to avoid drilling into Docker for most Central tasks.
- Central web worked at:
  - `https://192.168.204.16:8443/vc/index.html`
  - `https://192.168.204.16:8443/admin/login.html`
- On Central, the useful helper commands were:
  - `./scripts/bootstrap.sh --print-forward-historian-cheatsheet`
  - `./scripts/bootstrap.sh --volttron-docker-serverkey`
  - `./scripts/bootstrap.sh --volttron-docker-agents`
  - `./scripts/bootstrap.sh --volttron-docker-agent-status`
  - `OFDD_VOLTTRON_AUTH_CREDENTIALS='<edge-public-key>' ./scripts/bootstrap.sh --volttron-docker-auth-add`
- On the Pi, the ForwardHistorian agent changed from `BAD` to `GOOD` after the Central auth add + agent restart.

### Edge to Central Forward Agent Auth Cheat Sheet

### 1) On the Central Docker host, get the Central server key via the Open-FDD helper

```bash
cd ~/open-fdd
./scripts/bootstrap.sh --volttron-docker-serverkey
```

PoC output seen during this run:

```text
j6yIJQ1dqOeqd1yJsQ5lzBq4gLZOnb2oCA6PeoAvJik
```

### 2) On the Central Docker host, confirm current Central agents

```bash
cd ~/open-fdd
./scripts/bootstrap.sh --volttron-docker-agent-status
```

PoC posture on `.16` at validation time:

- `platform.historian` → `GOOD`
- `volttron.central` → `GOOD`

### 3) On the Boss Pi, go to VOLTTRON and activate the environment

```bash
cd ~/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate
mkdir -p configs
```

### 4) Create the Forward Historian config

```bash
nano configs/forward-to-central.json
```

Template:

```json
{
  "destination-vip": "tcp://192.168.204.16:22916",
  "destination-serverkey": "j6yIJQ1dqOeqd1yJsQ5lzBq4gLZOnb2oCA6PeoAvJik",
  "capture_log_data": false
}
```

Important note:

- The edge ForwardHistorian uses the Central VIP socket (`tcp://192.168.204.16:22916`), not the Central web UI URL.
- The edge VCP / Central-control config separately used:
  - `volttron-central-address = https://192.168.204.16:8443`

### 5) Install and start the Forward Historian on the Pi

```bash
vctl install --agent-config configs/forward-to-central.json services/core/ForwardHistorian --tag forward-to-central
vctl start --tag forward-to-central
vctl status
```

### 6) Get the Pi forwarder public key

```bash
vctl auth publickey --tag forward-to-central
```

PoC output seen during this run:

```text
kVT4pZVTUlS72U1CccZJk8nR0rIVdpEoMqTGpeBH6k4
```

### 7) Back on Central, add the Pi forwarder key without drilling into Docker

```bash
cd ~/open-fdd
OFDD_VOLTTRON_AUTH_CREDENTIALS='kVT4pZVTUlS72U1CccZJk8nR0rIVdpEoMqTGpeBH6k4' ./scripts/bootstrap.sh --volttron-docker-auth-add
```

Expected shape:

```text
added entry {'credentials': 'kVT4pZVTUlS72U1CccZJk8nR0rIVdpEoMqTGpeBH6k4', 'enabled': True}
```

### 8) Back on the Boss Pi, restart the Forward Historian

```bash
vctl stop --tag forward-to-central
vctl start --tag forward-to-central
vctl status
```

PoC result after this step:

- `forward-to-central` → `GOOD`

### 9) Quick validation

On the Boss Pi:

```bash
vctl status
```

Healthy PoC posture included:

- `platform.bacnet_proxy` → `GOOD`
- `platform.driver` → `GOOD`
- `vcp` → `GOOD`
- `forward-to-central` → `GOOD`

On the Central Docker host via Open-FDD helper:

```bash
cd ~/open-fdd
./scripts/bootstrap.sh --volttron-docker-agent-status
```

### Where the Open-FDD helper scripts were good

They were good for:

- server key retrieval
- central agent list / status
- auth add for the edge forwarder key
- cheat-sheet reminders of the edge ↔ central flow

### Where the Open-FDD helper scripts fell short

At this PoC stage, they still fell short on:

- a clean one-command log tail for the current `volttron-docker` layout
- a one-command proof that forwarded historian data landed in Central storage

Observed shortfall:

- `./scripts/bootstrap.sh --volttron-docker-tail-logs` looked for a Central log path that did not exist in the current container layout

### Important recreate notes

- Treat `~/open-fdd` on `.16` as the control surface for Central helper commands.
- Treat the Pi `~/volttron` as the control surface for native edge commands.
- For this PoC, the critical auth bridge was the ForwardHistorian public key add on Central.
- If the forwarder is `BAD`, first check whether its public key has been added on Central, then restart the forward agent on the Pi.
