# VOLTTRON 9.x bosspi GL36-ish request + trim/respond agents handoff

_Last updated: 2026-04-09_

## Executive summary

Two additional Python VOLTTRON agents were added on Raspberry Pi host `ben@192.168.204.12` to extend the working BACnet bench:

1. **GL36 VAV request agent**
   - subscribes to one or more VAV Platform Driver topics
   - computes per-VAV **cooling requests** and **pressure requests** using a practical GL36-style interpretation from the Java/Niagara reference
   - publishes aggregated request totals for AHU supervisory logic

2. **GL36 AHU trim/respond agent**
   - subscribes to the AHU Platform Driver topic plus the aggregated VAV request summary
   - computes **recommended** duct static pressure and supply air temperature reset setpoints
   - defaults to **publish/log only** mode for safety; it does **not** command live writes unless explicitly enabled later

This is intentionally a **safe demo implementation** for the bench. It is real VOLTTRON code, installed into the live platform, and observed running without errors in the current VOLTTRON log.

---

## Reference used and practical GL36 control intent

Primary external reference:

- `https://github.com/bbartling/niagara4-vibe-code-addict/blob/develop/README_TRIM_RESPOND.md`

Practical logic inferred from that reference:

### 1) VAV box zone request generator

For each VAV, calculate two independent supervisory outputs:

- **Cooling / SAT requests**
  - 3 requests if zone temp is well above cooling setpoint for a persistence period
  - 2 requests if moderately above setpoint for a persistence period
  - 1 request if the zone cooling loop is saturated
  - 0 otherwise

- **Static pressure requests**
  - 3 requests if measured flow is far below flow setpoint while damper is near full open for a persistence period
  - 2 requests if measured flow is moderately below setpoint while damper is near full open for a persistence period
  - 1 request if damper is simply near full open
  - 0 otherwise

This bench implementation uses the same basic thresholds described in the reference:

- cooling thresholds in imperial mode: `+5 F => 3 req`, `+3 F => 2 req`, `ZoneDemand > 95% => 1 req`
- pressure thresholds: `flow/setpoint < 0.50 and damper >= 95% => 3 req`, `flow/setpoint < 0.70 and damper >= 95% => 2 req`, `damper >= 95% => 1 req`
- hysteresis and persistence are included in simplified form

### 2) AHU duct static pressure reset (trim & respond)

- when total pressure requests are low or zero, the AHU should **trim down** duct static pressure setpoint
- when requests exceed the ignored-request threshold, the AHU should **respond upward**
- the response magnitude is capped by a configurable max-per-interval

Bench demo configuration currently uses these imperial-style example values:

- `SPmin = 0.5 in.w.c.`
- `SPmax = 1.5 in.w.c.`
- `SPtrim = -0.04 in.w.c. per interval`
- `SPres = +0.06 in.w.c. per excess request`
- `SPres-max = +0.15 in.w.c. per interval`

### 3) AHU supply air temperature reset (trim & respond)

The same trim/respond pattern is applied to SAT setpoint recommendations, but the sign is inverted from static pressure logic:

- when cooling requests are low or zero, SAT setpoint can **trim upward** a bit
- when cooling requests accumulate, SAT setpoint should **respond downward** to deliver colder air

Bench demo configuration currently uses:

- `SAT min = 52 F`
- `SAT max = 62 F`
- `trim = +0.5 F per interval`
- `respond = -1.0 F per excess request`
- `respond_max = 3.0 F per interval`

---

## Live bench context used

Working VOLTTRON base on the Pi:

- repo root: `/home/ben/volttron`
- virtualenv: `/home/ben/volttron/env`
- `VOLTTRON_HOME=/home/ben/.volttron`
- platform is already running with BACnet Proxy, Platform Driver, listener, and prior Ben CSV logger demo agent

Current bench devices actually available through Platform Driver:

- `BensFakeAHU` topic: `devices/BensFakeAHU/all`
- `Zone1VAV` topic: `devices/Zone1VAV/all`

Current real point names from the bench registries:

### Zone1VAV

- `ZoneTemp`
- `ZoneCoolingSpt`
- `ZoneDemand`
- `VAVFlow`
- `VAVFlowSpt`
- `VAVDamperCmd`

### BensFakeAHU

- `DAP_SP`
- `SAT_SP`
- `DAP_P`
- `SA_T`
- `SF_S`
- `SF_C`
- plus other AHU telemetry already exposed by Platform Driver

---

## New Pi source paths

### 1) GL36 VAV request agent

Project root:

- `/home/ben/volttron/volttron_data/ben_bacnet/gl36_vav_request_agent`

Files:

- `/home/ben/volttron/volttron_data/ben_bacnet/gl36_vav_request_agent/setup.py`
- `/home/ben/volttron/volttron_data/ben_bacnet/gl36_vav_request_agent/config`
- `/home/ben/volttron/volttron_data/ben_bacnet/gl36_vav_request_agent/gl36_vav_request/__init__.py`
- `/home/ben/volttron/volttron_data/ben_bacnet/gl36_vav_request_agent/gl36_vav_request/agent.py`

Installed identity/tag observed:

- VIP identity: `gl36.vav.requests`
- tag: `gl36-vav-requests`
- install UUID from install output: `10d3aa3d-c5fa-4c6f-903a-46d5415cd00b`

Published topics:

- `gl36/vav/request_summary`
- `gl36/vav/request_details`

### 2) GL36 AHU trim/respond agent

Project root:

- `/home/ben/volttron/volttron_data/ben_bacnet/gl36_ahu_trim_respond_agent`

Files:

- `/home/ben/volttron/volttron_data/ben_bacnet/gl36_ahu_trim_respond_agent/setup.py`
- `/home/ben/volttron/volttron_data/ben_bacnet/gl36_ahu_trim_respond_agent/config`
- `/home/ben/volttron/volttron_data/ben_bacnet/gl36_ahu_trim_respond_agent/gl36_ahu_trim_respond/__init__.py`
- `/home/ben/volttron/volttron_data/ben_bacnet/gl36_ahu_trim_respond_agent/gl36_ahu_trim_respond/agent.py`

Installed identity/tag observed:

- VIP identity: `gl36.ahu.trimrespond`
- tag: `gl36-ahu-trimrespond`
- install UUID from install output: `e5d3ab8d-ab93-4908-9b94-64cd7d0dcb23`

Published topic:

- `gl36/ahu/recommendations`

---

## Exact install/start commands used on the Pi

```bash
ssh ben@192.168.204.12
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate

python scripts/install-agent.py \
  -s /home/ben/volttron/volttron_data/ben_bacnet/gl36_vav_request_agent \
  -c /home/ben/volttron/volttron_data/ben_bacnet/gl36_vav_request_agent/config \
  -i gl36.vav.requests \
  --tag gl36-vav-requests \
  --start

python scripts/install-agent.py \
  -s /home/ben/volttron/volttron_data/ben_bacnet/gl36_ahu_trim_respond_agent \
  -c /home/ben/volttron/volttron_data/ben_bacnet/gl36_ahu_trim_respond_agent/config \
  -i gl36.ahu.trimrespond \
  --tag gl36-ahu-trimrespond \
  --start
```

---

## Verification evidence from the live VOLTTRON log

Log file:

- `/home/ben/.volttron/volttron.log`

Observed clean startup and live execution lines for the new agents:

```text
2026-04-09 15:12:09,427 (gl36_vav_requestagent-0.1 29196 [48]) __main__ INFO: Subscribed to devices/Zone1VAV/all for Zone1VAV
2026-04-09 15:12:20,672 (gl36_vav_requestagent-0.1 29196 [176]) __main__ INFO: GL36 VAV summary: active=1 pressure_total=0 cooling_total=0
2026-04-09 15:12:28,020 (gl36_ahu_trim_respondagent-0.1 29215 [49]) __main__ INFO: GL36 AHU trim/respond agent started in recommendation mode=True
2026-04-09 15:12:58,032 (gl36_ahu_trim_respondagent-0.1 29215 [105]) __main__ INFO: GL36 AHU recommendation: pressure_req=0 cooling_req=0 static 1.000->0.960 sat 55.0->55.5 mode=publish_only
```

Interpretation:

- VAV request agent is receiving Zone1VAV publishes and aggregating results
- AHU trim/respond agent is receiving both AHU telemetry and VAV summary data
- AHU logic is generating setpoint recommendations
- current observed bench state generated **0 pressure requests** and **0 cooling requests**, so the AHU recommendation was to trim static pressure downward and trim SAT upward
- no new traceback/error evidence was observed for these two new agents during the verified startup/run window

Important caveat:

- the full platform log contains older unrelated tracebacks from earlier work and other agents, so only use the time window around the GL36 agent install/run when claiming the new work was error-free

---

## What is implemented now

### Working now

- real VOLTTRON Python package for a **VAV request-counting / aggregation agent**
- real VOLTTRON Python package for an **AHU trim/respond supervisory agent**
- both installed into the live Pi platform
- both confirmed publishing/logging in `volttron.log`
- bench-safe behavior: **publish recommendations, do not write live setpoints by default**
- configuration structure already supports scaling to many VAVs by adding more entries to the config list

### Future-ready framework, not fully realized yet

- actual closed-loop live writing of `DAP_SP` and `SAT_SP` back through Platform Driver is **not enabled by default**
- only **one VAV** currently exists on the bench, so true multi-zone summation and ignored-request tuning are not yet meaningfully exercised
- SAT trim/respond is implemented as a practical supervisory pattern, but not a full site-specific Guideline 36 sequence with all occupancy/economizer/heating-mode safeguards
- no auto-discovery/semantic auto-mapping is wired into the agents yet; point names are still config-driven
- no persistence of internal timers/state across agent restart yet

---

## Safe command vs recommendation mode

Current safety posture:

- `write_recommendations` in the AHU agent config is set to `false`
- the agent therefore runs in **publish_only** mode
- it computes and publishes recommended reset setpoints, but it does **not** issue live writes to `BensFakeAHU`

Why this was chosen:

- the bench currently includes fake devices and only one VAV
- there is no need to risk accidental control interaction just to validate supervisory math
- recommendation mode is the honest/safe default for a first pass

If live writes are ever enabled later, do it deliberately and document the exact risk boundary.

---

## Config examples for scaling to many VAVs

The VAV request agent accepts a `vavs` list. To scale, add more objects with each VAV topic and point mapping.

Example pattern:

```json
{
  "vavs": [
    {
      "name": "Zone1VAV",
      "topic": "devices/Zone1VAV/all",
      "zone_temp_point": "ZoneTemp",
      "zone_cooling_setpoint_point": "ZoneCoolingSpt",
      "zone_demand_point": "ZoneDemand",
      "vav_flow_point": "VAVFlow",
      "vav_flow_setpoint_point": "VAVFlowSpt",
      "vav_damper_cmd_point": "VAVDamperCmd"
    },
    {
      "name": "Zone2VAV",
      "topic": "devices/Zone2VAV/all",
      "zone_temp_point": "ZoneTemp",
      "zone_cooling_setpoint_point": "ZoneCoolingSpt",
      "zone_demand_point": "ZoneDemand",
      "vav_flow_point": "VAVFlow",
      "vav_flow_setpoint_point": "VAVFlowSpt",
      "vav_damper_cmd_point": "VAVDamperCmd"
    }
  ]
}
```

This is intentionally name-driven so mixed vendors can be handled as long as the right point names are mapped in config.

---

## How AI could know what AHU/VAV points to use automatically

This is the next important layer: **semantic point selection**.

### Preferred approach: BRICK + Haystack

A robust AI workflow would not hard-code vendor point names forever. Instead it would:

1. identify equipment in a graph
   - AHU instance
   - VAV instances served by that AHU
2. identify semantically relevant points
   - on VAVs: zone temp, zone cooling setpoint, cooling demand, airflow, airflow setpoint, damper command
   - on AHU: duct static pressure setpoint, SAT setpoint, supply fan status/command, maybe SAT feedback, OAT, occupancy
3. resolve semantic points to live telemetry/write paths
   - BRICK relationships + tags
   - Haystack tags and refs
   - a mapping layer to BACnet object/property or Platform Driver point names
4. populate the VOLTTRON config automatically

### Why BRICK fits well

BRICK is good for:

- equipment typing (`brick:AHU`, `brick:VAV`)
- point typing (`brick:Zone_Air_Temperature_Sensor`, `brick:Damper_Position_Command`, `brick:Discharge_Air_Static_Pressure_Setpoint`, `brick:Supply_Air_Temperature_Setpoint`)
- relationships such as which VAVs are fed by which AHU

That enables an AI agent to query:

- “find all VAVs served by AHU-X”
- “for each VAV, get zone temp + cooling demand + damper cmd + airflow + airflow setpoint”
- “for AHU-X, get duct static pressure setpoint and SAT setpoint points”

### Why Haystack helps

Haystack is very practical for operational tagging and point-role identification. If a site already uses Haystack tags, an AI pipeline can match points through tags like:

- `ahu`, `vav`, `zone`, `temp`, `sp`, `cmd`, `sensor`, `flow`, `damper`, `discharge`, `static`

Haystack is often easier for field-facing metadata normalization, while BRICK is stronger for graph relationships and richer ontology.

### Where 223P / DBO can help

- **ASHRAE 223P** is useful for richer graph semantics around systems, connections, and formal building topology
- **DBO / digital-building ontologies** can help normalize enterprise-scale naming/models and vendor abstractions

Practical recommendation:

- use **BRICK** as the equipment/point relationship backbone
- accept **Haystack** tags as an equally valuable operational metadata source
- optionally enrich with **223P/DBO** where topology/formal systems modeling matters

### What auto-mapping would output for these agents

Ideally, the AI would generate the same config files now written by hand:

- list of VAV topics and point names for the request agent
- AHU topic and point names for the trim/respond agent
- confidence scores and human-review notes for ambiguous mappings

---

## Useful commands for future OpenClaw sessions

### Check source on Pi

```bash
ssh ben@192.168.204.12
ls -R /home/ben/volttron/volttron_data/ben_bacnet/gl36_vav_request_agent
ls -R /home/ben/volttron/volttron_data/ben_bacnet/gl36_ahu_trim_respond_agent
```

### Watch GL36 log activity

```bash
grep -n 'gl36_vav_requestagent\|gl36_ahu_trim_respondagent\|GL36 VAV summary\|GL36 AHU recommendation' /home/ben/.volttron/volttron.log | tail -n 100
```

### If you need to reinstall after code edits

```bash
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate

python scripts/install-agent.py \
  -s /home/ben/volttron/volttron_data/ben_bacnet/gl36_vav_request_agent \
  -c /home/ben/volttron/volttron_data/ben_bacnet/gl36_vav_request_agent/config \
  -i gl36.vav.requests \
  --tag gl36-vav-requests \
  --force \
  --start

python scripts/install-agent.py \
  -s /home/ben/volttron/volttron_data/ben_bacnet/gl36_ahu_trim_respond_agent \
  -c /home/ben/volttron/volttron_data/ben_bacnet/gl36_ahu_trim_respond_agent/config \
  -i gl36.ahu.trimrespond \
  --tag gl36-ahu-trimrespond \
  --force \
  --start
```

---

## OpenClaw handoff notes

If another OpenClaw instance continues this work, do these checks first:

1. SSH to `ben@192.168.204.12`
2. `cd /home/ben/volttron && export VOLTTRON_HOME=/home/ben/.volttron && source env/bin/activate`
3. inspect source under:
   - `/home/ben/volttron/volttron_data/ben_bacnet/gl36_vav_request_agent`
   - `/home/ben/volttron/volttron_data/ben_bacnet/gl36_ahu_trim_respond_agent`
4. inspect live bench topics in `/home/ben/.volttron/volttron.log`
5. verify current point names still match the Platform Driver registries:
   - `/home/ben/volttron/volttron_data/ben_bacnet/registry_configs/zone1vav.csv`
   - `/home/ben/volttron/volttron_data/ben_bacnet/registry_configs/bensfakeahu.csv`
6. keep recommendation mode unless Ben explicitly wants controlled write testing
7. if scaling to more VAVs, update the request-agent config first before changing logic
8. if semantic auto-mapping is added, keep the final generated config files backed up in this Windows docs folder too

Most likely next upgrades:

- add a more explicit RPC/status interface for both agents
- persist internal timers/state
- add occupancy/fan/economizer safeguards around SAT reset
- test with more than one VAV
- optionally integrate BRICK/Haystack query output into config generation
