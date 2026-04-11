# App 7 model-context notes

This file is the **big stuff only** context for future OpenClaw/model sessions.

## Primary source-of-truth code

The codebase that matters is:

- `volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/agent.py`
- `volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/webroot/app7/index.html`
- `volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/webroot/app7/app.js`
- `volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/webroot/app7/styles.css`

Ignore old prototype patterns outside that path.

## Current app shape

- VOLTTRON-hosted BAS Lite app on `bosspi`
- route: `http://192.168.204.12:8080/app7/index.html`
- sidebar intentionally simple:
  - theme toggle
  - equipment tree
- main dashboard repopulates for selected device
- Plotly trend view
- simple setpoint write box
- alarms/trends/high-low limits can be configured via OpenClaw chat instead of heavy UI forms

## Pi / service posture

- Pi host: `bosspi`
- main Linux service: `volttron.service`
- VOLTTRON web bind enabled at `http://192.168.204.12:8080`
- app 7 runs as agent `ben.app7.web`
- core dependencies expected healthy:
  - `platform.driver`
  - `platform.bacnet_proxy`
  - listener
  - GL36 agents

## Bench BACnet devices

Current known devices:

- `BensFakeAHU` → `192.168.204.13` / device `3456789`
- `Zone1VAV` → `192.168.204.14` / device `3456790`

## Data / retention posture

Current intent is Pi-friendly / SD-card-friendly:

- dashboard and trend state are bounded/in-memory first
- current target shape:
  - 5-minute trend handling
  - 31-day retention goal
- this is **not** a finished historian DB yet
- file logging should be deliberate, not noisy by accident
- advanced users may prefer journald/systemd controls for retention/rotation

## Proven capabilities

- live BACnet-backed dashboard data from the 2 bench devices
- Plotly trend rendering
- real writable BACnet setpoint path via Platform Driver
- verified example: `Zone1VAV::ZoneCoolingSpt` written successfully through app 7 / VOLTTRON / Platform Driver

## Alarm / trend / SMTP posture

For this bench phase, OpenClaw chat is an acceptable operator/config surface for:

- high limits
- low limits
- alarm enable/disable
- retention changes
- SMTP dial-out setup/testing

This is cleaner than forcing half-built config forms into the UI.

## Performance lessons

The browser lag / `ERR_INSUFFICIENT_RESOURCES` issue was not just "slow Pi".

It was heavily driven by frontend behavior causing overlapping request bursts.

### What helped

- remove click-time loading splash after initial load
- cache static-ish data client-side
- keep selected device/point in JS state
- use selective refresh instead of full-page rebuild logic
- use `Plotly.react()` instead of recreating the chart every click
- dedupe trend/setpoint fetches
- allow only one background refresh at a time
- no-op clicks should not refetch
- batch renders

## What not to do

### Do not do these again

- do **not** hammer VOLTTRON web service with many overlapping endpoint calls on every click
- do **not** rebuild the whole app shell on trivial interactions unless necessary
- do **not** let background refresh stomp form inputs while the user is typing
- do **not** leave old prototype code paths in the main app-7 directory if they are no longer source-of-truth
- do **not** trust a redeploy without checking the **actual installed Pi file** when behavior seems unchanged
- do **not** assume browser cache is innocent; hard refresh (`Ctrl+F5`) matters after JS changes
- do **not** leave duplicated/junk JS tails in `app.js`; this caused multiple browser syntax failures during iteration
- do **not** overbuild operator config UI for this 2-device bench if OpenClaw chat is the simpler tool

## Known rough edges / next clean step if needed

If frontend request pressure still misbehaves after caching/single-flight fixes, the next strong move is:

- create one combined dashboard endpoint for startup/device refresh

That would reduce request fan-out further and simplify the browser logic.

## Caddy / reverse proxy note

Caddy was discussed as a cleaner root-path entry option so `http://192.168.204.12/` could forward to app 7, but that was **not fully implemented yet** in this workstream. Current guaranteed working path remains:

- `http://192.168.204.12:8080/app7/index.html`
