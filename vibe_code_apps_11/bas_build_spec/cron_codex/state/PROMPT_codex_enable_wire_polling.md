# Codex wake — enable BACnet wire polling (manual fallback)

> **Prefer autonomous mode:** set `BAS_BACNET_AUTO_COMMISSION=true` in `cron_codex/.env` — worker `bas_bacnet_auto_commission.sh` arms wire every 5 min + before each wake. Use **this prompt** only when auto mode is off or failed.

> Day-to-day Who-Is is the **5-minute worker** + dashboard. See `memory/commissioning/ELECTRICAL_PHASE_ARCHITECTURE.md`.

**Manual paste:** only when the human message explicitly authorizes Who-Is on this OT LAN.

Paste into **manual wake** (`MINI_INVOCATIONS_PER_WAKE=1` recommended):

```
Human authorization (required): I have checked BOTH boxes in BUILD_CHECKPOINTS.md § BACnet lab sign-off and authorize BACnet Who-Is on the bind in PHASE_NOTEPAD.md § A. Proceed with wire enablement.

Read: PHASE_NOTEPAD.md § A and § C, PROMPT_enable_bacnet_polling.md, bacnet-driver-lifecycle, GUARDRAILS.md.

One slice — enable wire polling (execute, do not only document):

CR=/home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex
BAS_BUILD=/home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec

1. In BUILD_CHECKPOINTS.md § BACnet lab sign-off: mark both [x] with today's UTC date and signed-off name if human provided it.

2. bash $CR/bin/bas_bacnet_authorize_wire.sh --yes

3. Update $CR/.env (create from env.example if missing) with bind from PHASE_NOTEPAD § A:
   BAS_BACNET_LAB_VERIFY=true
   BAS_BACNET_APP_NAME=<sensible local app name>
   BAS_BACNET_DEVICE_INSTANCE=100
   BAS_BACNET_BIND_ADDRESS=<exact bind from notepad § A>

4. In $BAS_BUILD/cron/jobs.json set job "bas-bacnet-discovery-poll" enabled: true (keep schedule every 5 minutes).

5. Run one-shot poll:
   BAS_CODEX_ENV_FILE=$CR/.env bash $CR/bin/bas_bacnet_discovery_poll.sh
   Verify memory/integrations/bacnet_discovery_latest.json has ok:true and devices.

6. Append summary to memory/integrations/bacnet.md and rough-in chat:
   cd /home/ben/bas_app && python3 scripts/post_rough_in_chat_report.py --file <short report>

7. Restart stack so UI reads discovery JSON:
   cd /home/ben/bas_app && ./scripts/local_stack.sh stop && ./scripts/local_stack.sh start
   curl -fsS http://127.0.0.1:8000/api/public/rough-in | check driver_mode_label and device statuses

If poll fails: log error in bacnet.md and chat; do not fake online status. May need CODEX_SANDBOX=danger-full-access for BACnet UDP on this host.

Do not check Phase 1 acceptance [x]. Append Done recently in BUILD_CHECKPOINTS.
```

## What runs without this prompt (AUTO_COMMISSION)

| Step | Worker | Codex |
|------|--------|-------|
| Sign-off + authorize + `.env` + enable poll | **`bas_bacnet_auto_commission.sh`** | Fixes failures only |
| Who-Is every 5 min | **`bas_bacnet_discovery_poll.sh`** | No |

## Manual prompt only (AUTO off)

| Step | Codex? | Notes |
|------|--------|--------|
| Check sign-off boxes | **Only if you say so in the wake** | Safety gate |
| `authorize_wire.sh --yes` | **Yes** | After your explicit authorization text |
| Edit `.env` | **Yes** | Not committed; Codex can write |
| Enable `jobs.json` poll | **Yes** | |
| Run Who-Is poll | **Yes** if sandbox allows UDP | May need `danger-full-access` in `.env` |
| Crontab scheduler | **Maybe** | Human should confirm `bas_cron_scheduler.sh run-due` in crontab |
| Physical field devices online | **No** | Your lab network |

## Human still does once

Confirm **crontab** runs the scheduler (e.g. every minute) so 5-minute poll job fires between Codex wakes.
