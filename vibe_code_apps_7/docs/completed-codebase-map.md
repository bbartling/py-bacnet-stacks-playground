# Completed codebase map

This file is for humans and future OpenClaw/model sessions.

It answers one question:

**Where is the completed app-7 codebase we actually care about?**

## Current completed codebase

### Backend / VOLTTRON web agent

- `volttron_data/ben_bacnet/app7_web_agent/setup.py`
- `volttron_data/ben_bacnet/app7_web_agent/MANIFEST.in`
- `volttron_data/ben_bacnet/app7_web_agent/config`
- `volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/agent.py`
- `volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/__init__.py`

### Frontend

- `volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/webroot/app7/index.html`
- `volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/webroot/app7/app.js`
- `volttron_data/ben_bacnet/app7_web_agent/app7_web_agent/webroot/app7/styles.css`

### Deployment / operator docs

- `README.md`
- `RECREATE.md`
- `deploy-app7-to-bosspi.ps1`
- `docs/tech-setup-cheatsheet.md`
- `docs/model-context-notes.md`
- `docs/backend-contract.md`
- `docs/architecture.md`
- `docs/alarm-model.md`
- `docs/hosting-options.md`

## What this means

If a future session wants to understand or modify app 7, it should start with the files above.

Do not hunt for old snapshots first.
Do not treat deleted archive material as required context.
Do not assume there is another hidden "real" codebase elsewhere in this folder.

## Human summary

This folder is supposed to be:

- current code
- current docs
- lessons learned
- recreate/deploy commands

Not:

- backup museum
- stale log dump
- many conflicting copies of app 7
