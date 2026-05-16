# Enable BACnet Who-Is every ~5 minutes (between Codex wakes)

Your rough-in UI is **current** (Wire off / Pending Who-Is, staged VAV/AHU `.13`). Who-Is does **not** run until you complete the steps below.

## What runs where

| Component | Role |
|-----------|------|
| **bas-bacnet-discovery-poll** (jobs.json) | Worker every **5 min** — Who-Is, no Codex cost |
| **bacnet_discovery_latest.json** | Last poll result — **Codex wakes read this** |
| **rough-in UI** | Reads same JSON when `bacnet_wire_authorized` exists |
| **Chat** | Poll posts only when discovery result **changes** |

## Steps (human)

```bash
# 1. Check both boxes in bas_build_spec/BUILD_CHECKPOINTS.md § BACnet lab sign-off

# 2. Authorize wire (interactive)
CR=/home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex
bash $CR/bin/bas_bacnet_authorize_wire.sh

# 3. Edit cron_codex/.env — use YOUR bind from PHASE_NOTEPAD § A
# BAS_BACNET_LAB_VERIFY=true
# BAS_BACNET_APP_NAME=...
# BAS_BACNET_DEVICE_INSTANCE=100
# BAS_BACNET_BIND_ADDRESS=<from PHASE_NOTEPAD>

# 4. Enable poll job in bas_build_spec/cron/jobs.json
#    "bas-bacnet-discovery-poll" -> "enabled": true

# 5. Scheduler must run often enough (crontab * * * * * bas_cron_scheduler.sh run-due)

# 6. One-shot test
BAS_CODEX_ENV_FILE=$CR/.env bash $CR/bin/bas_bacnet_discovery_poll.sh
cat ../memory/integrations/bacnet_discovery_latest.json

# 7. Restart bas_app backend to pick up discovery overlay
cd /home/ben/bas_app && ./scripts/local_stack.sh stop && ./scripts/local_stack.sh start
```

## Codex can run the enablement (if you authorize in the wake message)

See **`PROMPT_codex_enable_wire_polling.md`** — single paste for Codex to execute steps 1–7. Requires you to say you checked sign-off and authorize Who-Is.

## Combined validation prompt (paste chat + Codex wake)

See **`PROMPT_bacnet_lab_validate.md`** — use after wire polling is enabled.
