# Vibe Code App 6 — VOLTTRON 9 AI-Assisted Edge Demo on `bosspi`

_Last updated: 2026-04-10_

This folder is the current **VOLTTRON-focused demo area** for the playground.

It shows how to move from simple Python/BACnet scripts into a more operational edge stack:

- **VOLTTRON 9.x** running on a Raspberry Pi bench host
- **Platform Driver** and **BACnet Proxy** handling live device access
- small custom Python agents built quickly with AI assistance
- safe supervisory logic that **publishes recommendations first** instead of blindly commanding equipment
- durable Windows-side notes and code backups so another OpenClaw or human can continue the work without re-discovering everything

This is not a polished product package. It is a practical, working **bench demo + tutorial trail**.

---

## What this app demonstrates

On Raspberry Pi host `ben@192.168.204.12` (`bosspi`), the VOLTTRON bench currently includes:

- a running VOLTTRON 9 platform at `/home/ben/volttron`
- `VOLTTRON_HOME=/home/ben/.volttron`
- core agents for:
  - `platform.bacnet_proxy`
  - `platform.driver`
  - `listener.bacnet`
- custom demo agents for:
  - CSV logging of Platform Driver publishes
  - GL36-ish VAV request aggregation
  - GL36-ish AHU trim/respond recommendation logic
- systemd boot persistence via `/etc/systemd/system/volttron.service`

In plain English:

1. VOLTTRON scrapes BACnet devices through its normal driver path.
2. Custom agents subscribe to those device topics.
3. One agent logs device values to CSV.
4. Another agent turns VAV telemetry into supervisory request counts.
5. Another agent converts those requests into AHU static-pressure and SAT reset recommendations.
6. The recommendation agent stays in **publish-only mode** by default for safety.

---

## Why this matters

The earlier vibe code apps in this repo teach direct BACnet scripting with BAC0 and BACpypes3.

This app is the next step:

- not just "read a BACnet point"
- but "run an edge platform that continuously ingests device data, hosts agents, and supports supervisory control logic"

That makes app 6 a good bridge between:

- **field scripting / Python learning**, and
- **real edge automation architecture**

---

## Bench status snapshot

As of the 2026-04-10 documentation pass, the Pi bench looked healthy after the prior systemd/autostart work:

- `volttron.service` was `active` and `enabled`
- the core and custom agents were running
- `vctl status` showed all expected agents `GOOD`
- the custom agents were still producing normal log activity after restart
- no new custom-agent traceback was found in the focused post-restart validation window

Important nuance:

- the historical VOLTTRON log contains earlier errors from development and restart work
- the current claim is **not** "the log has never had errors"
- the claim is that the custom agents and platform path looked clean in the latest focused overnight re-check after the service came back and the bench had been running stably

See the durable architecture/handoff note in this folder for exact evidence and commands.

---

## Folder contents

### Core handoff/tutorial notes

- `README.md`
  - you are here
- `VOLTTRON-9-bosspi-demo-agent-handoff.md`
  - what the CSV logger agent does, how it was installed, and how to inspect it
- `VOLTTRON-9-bosspi-GL36-agents-handoff.md`
  - the GL36-ish VAV request and AHU trim/respond agents, logic, safety mode, and future direction
- `VOLTTRON-9-bosspi-systemd-and-ops-notes-2026-04-09.md`
  - systemd persistence and day-2 operations on the Pi
- `VOLTTRON-9-bosspi-agent-source-backup-2026-04-09.md`
  - Windows-side source/config backup for the installed custom agents
- `VOLTTRON-9-bosspi-systemd-unit-2026-04-09.service`
  - saved copy of the systemd unit
- `2026-04-10-openfdd-volttron-architecture-notes.md`
  - durable Open-FDD + VOLTTRON architecture notes and next-step guidance
- `2026-04-10-bosspi-native-recreate-runbook.md`
  - exact SSH, `vctl`, systemd, BACnet proxy, Platform Driver, and custom-agent recreate steps for the current working native Pi setup

### Legacy/older backup note variants

- `VOLTTRON-9-bosspi-demo-agent-source-backup.md`
- `VOLTTRON-9-bosspi-GL36-agent-source-backup.md`

Keep the dated files as the preferred reference when they overlap.

---

## The shortest path to understanding the live demo

If you only have a few minutes, read these in order:

1. `VOLTTRON-9-bosspi-systemd-and-ops-notes-2026-04-09.md`
2. `VOLTTRON-9-bosspi-demo-agent-handoff.md`
3. `VOLTTRON-9-bosspi-GL36-agents-handoff.md`
4. `2026-04-10-openfdd-volttron-architecture-notes.md`

That gets you:

- platform lifecycle and operations
- what the custom agents do
- how the bench is wired today
- where Open-FDD could fit into the architecture next

---

## How to inspect the live Pi bench

SSH into the Pi:

```bash
ssh ben@192.168.204.12
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate
```

### Check service status

```bash
systemctl status volttron.service
systemctl is-enabled volttron.service
systemctl is-active volttron.service
```

### Check agents

```bash
vctl status
vctl list
```

Expected running identities/tags include:

- `platform.bacnet_proxy` / `bacnet-proxy`
- `platform.driver` / `platform-driver`
- `listener.bacnet` / `listener-bacnet`
- `ben.csv-logger` / `ben-csv-logger`
- `gl36.vav.requests` / `gl36-vav-requests`
- `gl36.ahu.trimrespond` / `gl36-ahu-trimrespond`

### Watch the main log

```bash
tail -f /home/ben/.volttron/volttron.log
```

Useful focused grep:

```bash
grep -n -E 'ben_csv_loggeragent|gl36_vav_requestagent|gl36_ahu_trim_respondagent|BACnet proxy RPC demo|GL36 VAV summary|GL36 AHU recommendation|Traceback|ERROR|Exception' /home/ben/.volttron/volttron.log | tail -n 120
```

### Inspect CSV output from the demo logger

```bash
ls -lah /home/ben/volttron/volttron_data/ben_bacnet/csv_logs
sed -n '1,5p' /home/ben/volttron/volttron_data/ben_bacnet/csv_logs/BensFakeAHU_$(date +%F).csv
sed -n '1,5p' /home/ben/volttron/volttron_data/ben_bacnet/csv_logs/Zone1VAV_$(date +%F).csv
```

---

## The custom agents, in plain language

### 1) Demo CSV logger agent

Purpose:

- subscribe to Platform Driver topics
- write device values to daily CSV files
- prove that a small custom VOLTTRON agent can observe bench traffic and persist it cheaply
- demonstrate direct `platform.bacnet_proxy` RPC reads at startup

Why it is useful:

- easy proof that BACnet ingestion is alive
- gives a simple historian-like trail without introducing a full database
- creates a concrete bridge between field telemetry and later analytics

Primary note:

- `VOLTTRON-9-bosspi-demo-agent-handoff.md`

### 2) GL36-ish VAV request agent

Purpose:

- listen to VAV telemetry
- convert zone/load/flow/damper conditions into cooling and pressure requests
- publish request totals that a supervisory layer can consume

Why it is useful:

- turns raw telemetry into control intent
- separates VAV evaluation from AHU supervisory action
- makes later scaling to many VAVs straightforward

Primary note:

- `VOLTTRON-9-bosspi-GL36-agents-handoff.md`

### 3) GL36-ish AHU trim/respond agent

Purpose:

- combine AHU telemetry with aggregated VAV request counts
- compute reset recommendations for:
  - duct static pressure setpoint
  - supply air temperature setpoint
- publish recommendations instead of commanding live writes by default

Why it is useful:

- demonstrates supervisory logic in a safe, inspectable way
- provides a solid starting point for later closed-loop tests
- clearly separates "recommend" from "control"

Primary note:

- `VOLTTRON-9-bosspi-GL36-agents-handoff.md`

---

## How this relates to the earlier vibe code apps

If you came here from the rest of the playground, the progression is roughly:

- `vibe_code_apps_1`
  - basic BAC0 and BACpypes3 reads/writes/releases
- `vibe_code_apps_2`
  - more structured polling / RPM-style workflows
- `vibe_code_apps_3`
  - priority array inspection and deeper control-state understanding
- `vibe_code_apps_4`
  - simple BACnet server/device examples, schedules, and weather ideas
- `vibe_code_apps_5`
  - point discovery / inventory workflows
- `vibe_code_apps_6`
  - operational edge orchestration with VOLTTRON agents and bench-safe supervisory logic

Useful cross-references in this repo:

- `C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_1\bac0_version_1.py`
- `C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_1\bacpypes3_version_1.py`
- `C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_2\bac0_version_2.py`
- `C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_2\bacpypes3_version_2.py`
- `C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_3\BAC0_version_3.py`
- `C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_3\bacypes_version_3.py`
- `C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_4\mini-schedule-calendar-device.py`
- `C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_4\mini_weather_device.py`
- `C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_5\bacpypes3_point_discover.py`

Those apps teach the direct protocol and Python side.

This app teaches what happens when you put those ideas inside a continuously running edge platform.

---

## Where Open-FDD fits

The strongest near-term combined architecture is not "replace VOLTTRON with Open-FDD" or "replace Open-FDD with VOLTTRON."

It is:

- **Open-FDD** for model-driven understanding of equipment, points, relationships, and validated addressing
- **VOLTTRON** for edge execution, local agent workflows, data movement, and supervisory algorithms

A practical split looks like this:

### Open-FDD is strongest at

- knowledge graph / device model management
- point semantics and relationships
- BACnet and Modbus address knowledge that has been validated against the live system
- FDD rules and validation workflows
- identifying which telemetry and control points are trustworthy enough to drive analytics or control logic

### VOLTTRON is strongest at

- running always-on edge agents
- local publish/subscribe pipelines
- safely hosting supervisory algorithms near the equipment
- coordinating ingestion, lightweight transformations, and action logic on a gateway or Pi
- acting even when cloud connectivity is intermittent

### Combined model

1. Open-FDD defines the building understanding.
2. Open-FDD validates the actual BACnet/Modbus addressing and point semantics.
3. That validated point map is exported to VOLTTRON-friendly config or topic-generation artifacts.
4. VOLTTRON agents consume that config to:
   - subscribe to the right telemetry
   - run edge algorithms
   - publish recommendations or actions
   - feed local or cloud pipelines
5. Results can flow back into Open-FDD for validation, fault context, and operator understanding.

That architecture is described in more detail in:

- `2026-04-10-openfdd-volttron-architecture-notes.md`

---

## Practical rules for future work

### Prefer recommendation mode first

For any new supervisory/control agent:

1. publish recommendations
2. validate them against telemetry and operator expectations
3. only then consider controlled writes

### Treat point mapping as a first-class problem

Do not bury equipment/point knowledge inside handwritten agent code if Open-FDD or a graph can provide a cleaner source of truth.

### Keep Windows-side backups

If source or config changes on the Pi, mirror the important parts back into this folder. That makes recovery and handoff much easier.

### Keep exact paths in the docs

Avoid fuzzy notes like "the VOLTTRON folder on the Pi." Use exact paths such as:

- `/home/ben/volttron`
- `/home/ben/.volttron`
- `/home/ben/volttron/volttron_data/ben_bacnet`

---

## Good next steps

If this demo continues, the highest-value next upgrades are:

1. generate VOLTTRON config from Open-FDD/graph output instead of hand-maintained point-name mappings
2. add more VAVs so request aggregation actually behaves like a multi-zone supervisory workflow
3. persist agent state/timers across restarts where it matters
4. add explicit health/status RPC methods for the custom agents
5. keep recommendation mode as the default until a deliberate closed-loop test plan exists
6. define a clean export contract from Open-FDD to VOLTTRON:
   - equipment identity
   - point semantics
   - validated address path
   - read/write capability
   - confidence / review status

---

## Handoff note for another OpenClaw

If another OpenClaw instance picks this up later, start here:

1. read this README
2. read `2026-04-10-openfdd-volttron-architecture-notes.md`
3. SSH to `ben@192.168.204.12`
4. verify `volttron.service` and `vctl status`
5. inspect `/home/ben/.volttron/volttron.log`
6. confirm whether the point names and bench devices still match the documented assumptions
7. only then change code or docs

That sequence will save a lot of wasted motion.
