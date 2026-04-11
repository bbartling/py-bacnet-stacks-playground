# App 7 recreate notes — VOLTTRON-hosted web app (option 1)

This is the quick recreate/install sequence for the app 7 VOLTTRON-hosted web agent.

---

## 1. Get onto the Pi and activate VOLTTRON

```bash
ssh ben@192.168.204.12
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate
```

---

## 2. Confirm base platform health

Use the proper Pi systemd-managed VOLTTRON base, not a random ad-hoc launch.

```bash
systemctl is-active volttron.service
systemctl status volttron.service --no-pager
vctl status
```

For the current app 7 bench, the Pi platform is expected to be running under `volttron.service` with web support enabled through the main VOLTTRON config.

---

## 3. Copy the agent source onto the Pi

Copy this folder:

`volttron_data/ben_bacnet/app7_web_agent`

Target path on Pi:

`/home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent`

---

## 4. Install the agent

```bash
vctl install --vip-identity ben.app7.web --tag ben-app7-web \
  /home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent \
  --config /home/ben/volttron/volttron_data/ben_bacnet/app7_web_agent/config
```

If reinstalling:

```bash
vctl remove --tag ben-app7-web
```

then install again.

---

## 5. Start and verify

```bash
vctl start --tag ben-app7-web
vctl status
```

Then check logs:

```bash
grep -n -E 'app7|web|Traceback|ERROR|Exception' /home/ben/.volttron/volttron.log | tail -n 80
```

---

## 6. Hit the routes

Expected paths:

- `/app7/`
- `/app7/api/health`
- `/app7/api/devices`
- `/app7/api/alarms/events`

The exact URL depends on the Pi’s web binding/TLS config.

---

## 7. What this first pass proves

This first pass is only meant to prove:

- VOLTTRON can host the static UI cleanly enough
- the route prefix is acceptable
- simple JSON endpoints are straightforward
- the deployment flow is tolerable on the Pi

It is **not** trying to prove the final full product yet.

---

## OpenClaw / tech commissioning notes

A future OpenClaw instance should be able to use this folder as context to:

- deploy/redeploy app 7 onto a proper `volttron.service` Pi base
- validate BACnet discovery / driver state
- configure trends and alarms through OpenClaw chat + notes
- assist a tech with SMTP dial-out testing during setup
- verify approved writable setpoints through the app 7 write path

## Notes

- static files are packaged through `MANIFEST.in`
- `agent.py` uses `enable_web=True`
- current static assets are served from `app7_web_agent/webroot/app7/`
- JSON endpoints are registered separately
- current bench data/trend cache is intentionally in-memory and bounded to reduce SD-card wear
- current config targets 5-minute trend handling with a 31-day retention goal, but the present bench implementation is still a lightweight runtime cache rather than a finished historian database
- another OpenClaw instance should be able to copy this folder, deploy the agent, configure alarm/trend posture, and assist with SMTP dial-out testing during setup
- writable BACnet setpoints should be verified only on approved adjustable points during commissioning; app 7 now includes a simple setpoints panel aimed at the real Platform Driver write path
- this is the explicit option-1 experiment before considering a split frontend/backend hosting model
