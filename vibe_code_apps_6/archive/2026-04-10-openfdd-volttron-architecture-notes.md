# Open-FDD + VOLTTRON architecture notes

_Date: 2026-04-10_
_Folder: `C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_6`_

This note is meant to be durable.

It is written so another OpenClaw instance, or a human returning later, can understand:

- the current VOLTTRON bench state
- what was re-checked during the overnight docs pass
- how Open-FDD and VOLTTRON could fit together cleanly
- what should happen next if this becomes a deeper implementation effort

---

## 1) Overnight re-check summary

### Pi / VOLTTRON host re-checked

Host:

- `ben@192.168.204.12`
- hostname: `bosspi`

Core paths:

- repo root: `/home/ben/volttron`
- runtime home: `/home/ben/.volttron`
- virtualenv: `/home/ben/volttron/env`
- custom bench content: `/home/ben/volttron/volttron_data/ben_bacnet`

### What was confirmed

On the focused re-check window:

- `volttron.service` was active and enabled
- the platform main process was up under systemd
- the expected agents were running:
  - `platform.bacnet_proxy`
  - `platform.driver`
  - `listener.bacnet`
  - `ben.csv-logger`
  - `gl36.vav.requests`
  - `gl36.ahu.trimrespond`
- agent health states showed `GOOD`
- the custom agents were still logging normal activity
- the post-restart window did **not** show new tracebacks for the custom agents

### Important log interpretation nuance

The full historical `volttron.log` contains earlier development/restart errors from 2026-04-09.

That is expected in a live bench buildout.

For the overnight documentation pass, the useful question was narrower:

> Is there evidence of new custom-agent or platform-path problems in the latest stable runtime window?

Answer from the focused re-check:

- **No obvious new custom-agent failures were found in the latest post-restart running window.**
- the bench looked stable enough to document as an operational demo
- older errors should remain documented as historical development context, not mistaken for current overnight regression evidence

### Exact commands used for the focused check

From the Windows workspace machine:

```powershell
$script = @'
set -e
hostname
(date || true)
printf '\n--- service ---\n'
systemctl is-active volttron.service || true
systemctl is-enabled volttron.service || true
systemctl --no-pager --full status volttron.service | sed -n '1,40p' || true
printf '\n--- git ---\n'
cd /home/ben/volttron && git status --short --branch || true
printf '\n--- agents ---\n'
export VOLTTRON_HOME=/home/ben/.volttron
. /home/ben/volttron/env/bin/activate
vctl status || volttron-ctl status || true
printf '\n--- recent volttron log ---\n'
tail -n 120 /home/ben/.volttron/volttron.log || true
printf '\n--- recent errors/warnings ---\n'
grep -n -E 'ERROR|Traceback|Exception|CRITICAL' /home/ben/.volttron/volttron.log | tail -n 60 || true
printf '\n--- custom agent focused ---\n'
grep -n -E 'ben_csv_loggeragent|gl36_vav_requestagent|gl36_ahu_trim_respondagent|BACnet proxy RPC demo|GL36 VAV summary|GL36 AHU recommendation|unhandled exception|Write attempt failed' /home/ben/.volttron/volttron.log | tail -n 120 || true
'@
ssh ben@192.168.204.12 bash -lc $script
```

### Useful evidence captured from that pass

Systemd showed:

- `/etc/systemd/system/volttron.service` loaded
- `active (running)`
- main PID under the VOLTTRON virtualenv
- all three custom agents running as child processes

`vctl status` showed all expected agents in `GOOD` health.

Focused log evidence showed continuing normal lines such as:

- `Logged 17 fields for BensFakeAHU ...`
- `Logged 6 fields for Zone1VAV ...`
- `GL36 VAV summary: active=1 pressure_total=0 cooling_total=0`
- `GL36 AHU recommendation: pressure_req=0 cooling_req=0 static 1.000->0.960 sat 55.0->55.5 mode=publish_only`

Those are the right kinds of lines for a healthy demo state.

---

## 2) What the current bench actually is

The current Pi setup is best understood as a **bench-safe edge orchestration demo**.

It is not yet a generalized production architecture.

### Live ingredients today

- BACnet devices exposed to VOLTTRON Platform Driver
- VOLTTRON topic-based telemetry flow
- custom agents that:
  - log device publishes to CSV
  - infer VAV pressure/cooling requests
  - compute AHU reset recommendations
- systemd boot persistence
- Windows-side doc/code backups in this folder

### Current strengths

- practical and inspectable
- close to real device behavior
- already running on edge hardware
- easy to explain
- safe default because the supervisory agent is still publish-only

### Current limitations

- point semantics are still largely hand-mapped in config
- only one VAV is currently participating, so request aggregation is not meaningfully stressed
- no formal config-generation pipeline from a graph/model source yet
- no closed-loop write workflow with proper guardrails, review, and rollback plan yet
- no rich historian/pipeline/observability layer beyond logs and CSV artifacts yet

---

## 3) Best combined Open-FDD + VOLTTRON story

The strongest open/free architecture idea is a division of labor.

### Open-FDD should own the building understanding

Open-FDD is a strong fit for:

- knowledge graphing
- semantic equipment and point relationships
- FDD logic and validation workflows
- data-model quality checks
- validated BACnet/Modbus addressing knowledge
- proving that a point is not just semantically plausible, but actually readable/writable in the live bench

That means Open-FDD should answer questions like:

- What equipment exists?
- Which VAVs are served by which AHU?
- Which points are zone temp, zone cooling setpoint, flow, static pressure setpoint, SAT setpoint, fan status, occupancy, etc.?
- What BACnet or Modbus path actually reaches those points?
- Which mappings are confirmed vs inferred?

### VOLTTRON should own edge execution

VOLTTRON is a strong fit for:

- edge agent runtime
- pub/sub data flow
- local supervisory and optimization algorithms
- on-prem data movement and transformations
- reliable always-on services on Pi/gateway hardware
- local action behavior even when cloud links degrade

That means VOLTTRON should answer questions like:

- How do we keep ingesting telemetry continuously?
- How do we run agents on a schedule or on publish events?
- How do we aggregate local signals?
- How do we compute recommendations or actions?
- How do we publish status, alarms, and outputs back to the local site?

### Clean one-sentence architecture

A good summary is:

> Open-FDD tells VOLTTRON what the building means and how to reach it; VOLTTRON uses that validated understanding to run edge algorithms and data pipelines safely.

That is the real synergy.

---

## 4) Proposed architecture pattern

## Pattern A — Open-FDD as source of truth, VOLTTRON as edge executor

This is the clearest near-term architecture.

### Step 1: Open-FDD models and validates the site

Open-FDD maintains:

- equipment graph
- point semantics
- point-to-equipment relationships
- validated BACnet/Modbus addressing
- confidence / validation status for each point

### Step 2: Open-FDD exports operational artifacts

Instead of requiring every VOLTTRON agent author to hand-wire point names, Open-FDD should export machine-usable artifacts such as:

- a JSON config for each supervisory use case
- point lists grouped by equipment role
- read/write path metadata
- units / type / scaling metadata
- confidence or review status

Example export concept:

```json
{
  "site": "bench-hvac",
  "ahu": {
    "name": "BensFakeAHU",
    "telemetry_topic": "devices/BensFakeAHU/all",
    "points": {
      "static_pressure_setpoint": {
        "point_name": "DAP_SP",
        "protocol": "bacnet",
        "validated": true,
        "writable": true
      },
      "supply_air_temperature_setpoint": {
        "point_name": "SAT_SP",
        "protocol": "bacnet",
        "validated": true,
        "writable": true
      }
    }
  },
  "vavs": [
    {
      "name": "Zone1VAV",
      "telemetry_topic": "devices/Zone1VAV/all",
      "points": {
        "zone_temp": "ZoneTemp",
        "zone_cooling_setpoint": "ZoneCoolingSpt",
        "zone_demand": "ZoneDemand",
        "airflow": "VAVFlow",
        "airflow_setpoint": "VAVFlowSpt",
        "damper_command": "VAVDamperCmd"
      }
    }
  ]
}
```

### Step 3: VOLTTRON consumes those artifacts

VOLTTRON agents then use generated config instead of hand-maintained guesses.

That means:

- less hard-coded site knowledge in code
- easier scaling to more equipment
- easier review of what the algorithm believes the system is
- better traceability when point mappings change

### Step 4: VOLTTRON executes edge logic

Examples:

- request aggregation
- trim/respond reset logic
- local fallback control recommendations
- edge optimization passes
- buffering/forwarding of telemetry
- local sanity checks and alerts

### Step 5: results flow back to Open-FDD and operators

Possible return paths:

- recommendation topics
- action audit logs
- fault context summaries
- derived telemetry
- validation feedback when a point mapping seems wrong in practice

This creates a virtuous loop:

- Open-FDD improves semantic truth
- VOLTTRON improves edge behavior
- each can inform the other

---

## 5) Edge vs cloud placement

The most practical architecture is not exclusively edge or exclusively cloud.

It is a layered model.

### Edge Open-FDD + edge VOLTTRON

Good for:

- local survivability
- immediate control-adjacent workflows
- sites with poor WAN reliability
- privacy-sensitive deployments

Tradeoffs:

- more software footprint at the edge
- local update/operations burden

### Cloud Open-FDD + edge VOLTTRON

Good for:

- central graph governance
- fleet-wide semantic normalization
- consistent validation workflows across many sites
- centralized rule/model improvement

Tradeoffs:

- requires a clean, reliable sync/export contract to the edge
- edge still needs enough local knowledge to function safely when disconnected

### Hybrid model: likely best long-term

A strong hybrid pattern is:

- **cloud Open-FDD** manages master semantic truth and site models
- **edge Open-FDD cache/materialization** carries the subset needed locally
- **edge VOLTTRON** executes telemetry, pipelines, and supervisory logic using that local validated subset

That gives:

- central intelligence and governance
- local resilience and execution

---

## 6) How Open-FDD could materially improve the current VOLTTRON bench

The biggest current weakness in the VOLTTRON demo is manual point/config wiring.

Open-FDD could improve that directly.

### A. Config generation for VOLTTRON agents

Instead of hand-writing:

- `ZoneTemp`
- `ZoneCoolingSpt`
- `VAVFlow`
- `DAP_SP`
- `SAT_SP`

Open-FDD should generate those mappings from validated graph knowledge.

### B. Validation before supervisory use

Before a point is used by a supervisory agent, Open-FDD should be able to say:

- the point exists in the model
- the address path was validated
- units/type look correct
- the point is attached to the expected equipment
- read/write behavior is known

That is a big quality upgrade over ad hoc manual mapping.

### C. Better multi-protocol story

Open-FDD is already naturally positioned to carry both BACnet and Modbus addressing knowledge.

That matters because VOLTTRON edge logic often should not care whether a signal came from BACnet or Modbus, as long as the semantic contract is clear.

Open-FDD could provide a normalized signal contract such as:

- `zone_temp`
- `discharge_static_pressure_setpoint`
- `supply_air_temperature_setpoint`
- `fan_status`

while hiding the protocol-specific path details behind the validated mapping layer.

### D. Better operator trust

If a trim/respond agent proposes a reset change, an operator should be able to see:

- which VAVs drove the request
- which points were used
- whether those points were graph-validated
- when the mappings were last confirmed

Open-FDD is well suited to hold and expose that traceability.

---

## 7) How VOLTTRON could materially improve Open-FDD

The relationship is not one-way.

VOLTTRON can strengthen Open-FDD too.

### A. Rich edge telemetry stream

VOLTTRON already gives a natural event stream and local runtime for:

- continuous point data
- derived signals
- edge summaries
- algorithm outputs

That can feed Open-FDD validation and FDD workflows.

### B. Local execution of derived logic

Open-FDD may know what should be checked.

VOLTTRON can host the local runtime that actually executes those checks or precomputes derived features near the equipment.

### C. Site survivability

If Open-FDD cloud services are remote, VOLTTRON can keep local functions alive and later backfill or resync results.

### D. Safe action pipeline

VOLTTRON can host a graded action ladder:

1. observe
2. recommend
3. require approval
4. write under guardrails

That is useful for any Open-FDD-driven optimization/control pathway.

---

## 8) Concrete implementation idea for the next real step

If this work continues, the best next architecture milestone is probably:

## Milestone: generated supervisory config from Open-FDD into VOLTTRON

### Goal

Replace handwritten point mappings in the current GL36-ish agents with generated config based on Open-FDD-validated equipment and point knowledge.

### Minimal deliverables

1. Define one export schema from Open-FDD to VOLTTRON.
2. Generate config for one AHU + one or more VAVs.
3. Update the VOLTTRON request and trim/respond agents to consume that schema cleanly.
4. Keep the AHU agent in publish-only mode.
5. Document evidence that generated mappings match live telemetry.

### Required export fields

At minimum, each exported point should include:

- site id
- equipment id / name
- semantic role
- local VOLTTRON topic or device name
- original BACnet/Modbus address reference
- units
- type
- read/write capability
- validation status
- last validated timestamp

### Why this is the right next step

Because it improves:

- correctness
- maintainability
- explainability
- scaling potential

without forcing an early jump into risky closed-loop control.

---

## 9) Guardrails if closed-loop control is ever tested later

If the AHU agent ever moves from publish-only to write mode, do not skip the safety work.

Required guardrails should include at least:

- explicit enable flag per site/equipment
- bounded min/max write limits
- fan/proof/occupancy checks
- stale-data detection
- write audit trail
- easy rollback path
- operator-visible recommendation vs actual write history
- clear distinction between inferred and validated point mappings
- rate limiting / write deadband
- site-specific review before activation

For this bench, the present default remains correct:

- **publish recommendations only**

---

## 10) Durable handoff checklist

If another OpenClaw session resumes this work later:

1. Re-check Pi runtime:
   - `ssh ben@192.168.204.12`
   - `systemctl status volttron.service`
   - `cd /home/ben/volttron && export VOLTTRON_HOME=/home/ben/.volttron && source env/bin/activate && vctl status`
2. Re-read these files in this folder:
   - `README.md`
   - `VOLTTRON-9-bosspi-demo-agent-handoff.md`
   - `VOLTTRON-9-bosspi-GL36-agents-handoff.md`
   - `VOLTTRON-9-bosspi-systemd-and-ops-notes-2026-04-09.md`
3. Confirm whether the bench still uses:
   - `BensFakeAHU`
   - `Zone1VAV`
   - the same point names/topics
4. Decide whether the next step is:
   - docs only
   - generated config
   - more devices/VAVs
   - Open-FDD integration
   - guarded write testing
5. Keep new findings mirrored back into this Windows folder, not only on the Pi.

---

## 11) Bottom-line architecture opinion

The most credible free/open-source service stack here is:

- **Open-FDD** as the semantic/model/validation/FDD brain
- **VOLTTRON** as the edge runtime and local execution layer

That pairing is stronger than either tool alone.

Open-FDD can answer:

- what the system is
- what the points mean
- how to reach them safely and correctly

VOLTTRON can answer:

- what to run continuously at the edge
- how to move and act on the data locally
- how to host algorithms and staged action behavior

If implemented well, Open-FDD becomes the trusted semantic contract and validation layer, while VOLTTRON becomes the practical edge worker that turns that contract into real operations.

That is the architecture direction worth keeping.
