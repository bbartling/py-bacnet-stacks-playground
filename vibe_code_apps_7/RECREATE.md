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
