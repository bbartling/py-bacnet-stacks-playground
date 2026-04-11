# app7_web_agent

VOLTTRON web-enabled agent for the app 7 option-1 experiment.

## Purpose

- serve static operator UI files from `webroot/`
- expose small JSON endpoints for UI data
- prove whether a VOLTTRON-hosted BAS Lite UI is clean enough for MVP use

## Installed route prefix

Configured by `config`:

- static UI: `/app7/`
- API examples: `/app7/api/health`, `/app7/api/devices`, `/app7/api/alarms/events`

## Key files

- `setup.py`
- `MANIFEST.in`
- `config`
- `app7_web_agent/agent.py`
- `webroot/index.html`
- `webroot/app.js`
- `webroot/styles.css`
