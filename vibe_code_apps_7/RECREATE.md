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

```bash
systemctl is-active volttron.service
vctl status
```

If the Platform Web Service Agent is not running, this app will not serve web content correctly.

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

## Notes

- static files are packaged through `MANIFEST.in`
- `agent.py` uses `enable_web=True`
- static assets are served from `webroot/`
- JSON endpoints are registered separately
- this is the explicit option-1 experiment before considering a split frontend/backend hosting model
