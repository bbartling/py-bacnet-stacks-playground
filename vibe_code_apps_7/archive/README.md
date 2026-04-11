# App 7 archive / checkpoint notes

This folder is the pause-point backup for the first live Pi run of **app 7 option 1** (VOLTTRON-hosted BAS Lite web app).

## What is in here

- `pi-volttron-config-2026-04-11.txt` — Pi VOLTTRON config snapshot after enabling web bind
- `proxy_scan_app7_2026-04-11-071948.csv` — BACnet proxy scan confirming the 2 bench devices during the app 7 run
- `volttron-log-snapshot-2026-04-11.log` — log snapshot pulled back from the Pi during the live app 7 iteration
- `2026-04-11-app7-pause-status.md` — short handoff note describing current state, what is working, and the next bug to fix

## Current pause-state summary

- app 6 remains the base on `bosspi`
- VOLTTRON web libraries were installed successfully with `bootstrap.py --web`
- the Pi is now listening on `http://192.168.204.12:8080`
- BACnet Proxy + Platform Driver + GL36 agents are running and seeing the 2 real bench devices
- `ben.app7.web` is installed and shows `GOOD`
- app 7 is using a lightweight in-memory/bounded retention posture for dashboard and trend state to help reduce Raspberry Pi SD-card wear
- the original `/app7` route bug from the first live run was fixed later in the same work stream; the archive here still preserves that earlier checkpoint context
