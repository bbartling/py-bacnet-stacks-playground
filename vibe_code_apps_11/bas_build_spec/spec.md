You are an expert software engineering agent building a Building Automation System (BAS) supervisory head-end web application.

Your task is to design, implement, test, and document a production-style BAS head-end and supervisory GUI inspired by a real construction specification for a DDC / Building Automation System. The goal is not to create a toy dashboard. The goal is to create a credible BAS software platform prototype with architecture, database models, APIs, UI workflows, permissions, alarms, trends, schedules, graphics, audit logging, and safe supervisory control workflows.

The system shall represent the head-end / supervisory level of a BAS. It should not depend on the graphical user interface for actual field control execution. Field controllers and equipment logic must be modeled as independent systems that can continue operating if the web GUI or server is unavailable. The GUI is for supervision, configuration, monitoring, scheduling, alarm review, trend review, reporting, and authorized operator interaction.

Build the project as a local-first web application suitable for a BAS workstation/server environment.

Recommended stack (intentionally generic — swap parts without rewriting domain rules):
- Backend: Python (required for this project). Expose a stable HTTP API; keep protocol drivers behind interfaces.
- Frontend: any modern SPA is acceptable; React + TypeScript is the default if no preference is stated.
- Primary database: PostgreSQL (or compatible) for configuration, users, audit, alarms metadata, schedules.
- Time-series telemetry: prefer a dedicated time-series store or extension (e.g. TimescaleDB on PostgreSQL, or another TSDB) behind a small ingestion/query abstraction so the rest of the app does not depend on vendor SQL.
- Realtime: WebSockets or Server-Sent Events for live point updates and alarm updates.
- Reverse proxy / TLS: Caddy is recommended for local and lab deployments — automatic HTTPS or [self-signed local TLS](https://caddyserver.com/docs/tls) with minimal configuration; nginx remains an acceptable alternative.
- Deployment: Docker Compose or equivalent for local-first workstation installs; document bare-metal run paths as well.
- Auth: secure username/password login (or stronger) with roles and permissions.
- Testing: backend unit tests, API tests, frontend component tests or Playwright end-to-end tests where practical.
- Include a seeded demo building with fake but realistic BAS data.

GENERIC ARCHITECTURE NOTES

- Treat the supervisory head-end as one service boundary; field execution stays on controllers or dedicated gateway processes.
- Any “driver” (BACnet, Modbus, REST equipment) should be optional, off by default, and replaceable without changing core domain models more than necessary.
- Prefer environment-based configuration (bind addresses, feature flags, driver endpoints) over hardcoded site constants.

Important: Do not require live BACnet hardware to run the application. Include a simulator/mock driver that generates realistic points, alarms, trends, and equipment states. Design the architecture so a real BACnet/IP, BACnet MS/TP gateway, Modbus gateway, or REST-based BAS driver could be plugged in later.

BACNET / BACPYES3 (OPTIONAL REAL DRIVER)

For concrete BACpypes3 client and sample device patterns (read, write, relinquish, read-property-multiple logging, priority array, schedule/calendar server, weather server), see **`bas_build_spec/bacnet_scripts.md`** in this repo. That file is reference material for a future BACnet driver or sidecar poller — not a runtime dependency of the default demo.

BACpypes3 (and similar BACnet/IP stacks) need the **local BACnet/IP bind string** so responses and broadcasts use the correct NIC and subnet. The project’s examples use `SimpleArgumentParser` and pass:

```text
--address <IP>/<prefix-length>[:UDPPort]
```

Example: `--address 192.168.204.18/24:47808` binds to IPv4 `192.168.204.18` on `/24` with BACnet UDP **47808** (standard BACnet/IP port; omit `:47808` only if your parser default matches). The IP must be an address **assigned to the host on the same L2/L3 segment as the BACnet devices**, not an arbitrary device IP.

Discovering the correct value on Linux (illustrative output from a lab workstation — **re-run `ip a` on the target machine**; interfaces and leases change):

```text
$ ip a
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    inet 127.0.0.1/8 scope host lo
2: enp3s0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    inet 192.168.204.18/24 metric 100 brd 192.168.204.255 scope global dynamic enp3s0
5: docker0: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc noqueue state DOWN group default
    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0
```

Operational rule: bind `--address` to the **interface that reaches the BACnet network** (here `enp3s0` / `192.168.204.18/24`), not to `docker0` or `lo`, unless BACnet traffic is intentionally routed/NATed through those. Multi-homed hosts must use the subnet that matches field devices (compare to device IPs in `bacnet_scripts.md` examples).

Other CLI flags used in the reference scripts (e.g. `--name`, `--instance`, `--debug`) identify the **local BACnet device object** this process presents on the wire; keep them unique per concurrently running BACpypes3 app on the same bind address.

PROJECT GOAL

Create a BAS supervisory head-end web application that provides:

1. Building/equipment navigation
2. Real-time point monitoring
3. BAS-style graphics
4. Alarms and alarm history
5. Trends and historical data export
6. Schedules and exception schedules
7. Setpoint/property adjustment workflows
8. Role-based access control
9. Audit/event logging
10. Simulated BACnet-style equipment and point data
11. Safe command/write workflow
12. Documentation and acceptance tests

The finished system should feel like a simplified modern BAS head-end similar in spirit to Niagara, Siemens, Schneider, Honeywell, or other commercial BAS front ends, but open-source-style and developer-friendly.

CORE DOMAIN MODEL

Implement database models or equivalent domain entities for:

Site
- id
- name
- description
- address
- timezone

Building
- id
- site_id
- name
- description
- building_number
- floor_count

Floor
- id
- building_id
- name
- level

Equipment
- id
- building_id
- floor_id optional
- name
- equipment_type
- description
- serving_area
- parent_equipment_id optional
- status
- communication_status
- alarm_status

Equipment types should include at least:
- AHU
- VAV
- Chiller
- Boiler
- Pump
- Cooling Tower
- Lighting Panel
- Generic Controller

Point
- id
- equipment_id
- name
- display_name
- description
- point_type
- object_type
- object_instance
- units
- present_value
- priority_array optional
- relinquish_default optional
- status_flags
- is_commandable
- is_trended
- is_alarmable
- last_updated
- source_protocol
- source_address
- writable_priority default 16 or configurable

Point types should include:
- analog_input
- analog_output
- analog_value
- binary_input
- binary_output
- binary_value
- multistate_input
- multistate_output
- multistate_value

Supervisory navigation tree (BAS-typical, beyond the minimum Site → Building → Floor → Equipment → Points)

Commercial BAS head-ends expose a **layered tree** so operators and engineers can find points by **facility role** and **protocol identity**, not only by physical location. The domain model and UI navigation should support:

- **Site → Building → (optional) System or discipline** — e.g. *HVAC*, *Central Plant*, *Lighting*, *Lab / Critical Ventilation*, *Electrical / Metering* — as a grouping node that contains equipment and cross-equipment summaries.
- **Floor → Space / Zone (optional)** — room or pressure zone labels where the building program uses them (labs, OR suites, data halls).
- **Equipment hierarchy** — parent/child equipment (e.g. plant → chiller → evaporator circuit; AHU → heating/cooling coil sub-components) using `parent_equipment_id` or equivalent.
- **Points** — leaves with display name, engineering units, commandable flag, trend/alarm flags, and **stale/offline** indication.
- **Network / driver facet (metadata on equipment or point)** — for BACnet: **device instance**, **IP or router path**, **object type + instance** (e.g. `analog-input:1`), **segment name** — so the same logical point appears in both the **operator tree** and the **protocol address** view (common in Niagara, Desigo, EcoStruxure, etc.).

Optional domain extension (recommended for real drivers and “networked” values):

- **SupervisoryLink** (or **PointFanOut** / **Binding**): `source_point_id`, one or more `target_point_id`, `enabled`, `write_priority` (BACnet-style), `min_write_interval_seconds`, `deadband` (for floats), `last_written_value`, `last_write_at`, `last_error`. Represents the head-end **pushing** a supervisory or field-captured value to another BACnet object (e.g. networked outside air).

TrendSample
- id
- point_id
- timestamp
- value
- quality/status

Telemetry ingestion and time-series storage (under the hood)

The head-end is not only an in-memory cache of present values. **Useful BAS sensors and outputs** (analog inputs/values tied to temperatures, flows, pressures, energy; key binary status; selected multistate modes) must be **persisted on a policy basis** to the time-series layer (TimescaleDB or equivalent) so trends, commissioning reports, energy analysis, and alarm forensics work after restarts.

- **Ingestion path:** driver or simulator → normalized **present-value + quality + timestamp** events → ingestion service → TSDB (and optional rollups). Configuration determines **which points** are historized (explicit list, `is_trended` flag, or template defaults per equipment type).
- **Correlation:** each sample remains joinable to `point_id`, `equipment_id`, building, and site for queries and exports.
- **Retention:** document default retention (e.g. raw 90 days + hourly rollups longer) as configurable.
- **Separation:** configuration and audit remain in PostgreSQL; high-volume telemetry in the TSDB abstraction — same pattern already recommended in the stack section above.

Alarm
- id
- point_id optional
- equipment_id optional
- alarm_type
- priority/severity
- state
- message
- active_timestamp
- acknowledged_timestamp
- returned_to_normal_timestamp
- acknowledged_by
- shelved_until optional
- instructions/operator_message optional

Schedule
- id
- name
- category
- equipment_id optional
- point_id optional
- weekly_schedule JSON
- exception_schedule JSON
- effective_date
- timezone
- enabled

CommandEvent / AuditLog
- id
- timestamp
- user_id
- action_type
- target_type
- target_id
- old_value
- new_value
- reason
- result
- source_ip/session info if available

User / Role / Permission
- Admin
- Engineer
- Operator
- ReadOnly
- AlarmOnly optional

ARCHITECTURE REQUIREMENTS

Create a clean project structure.

Backend should include:
- API routes/controllers
- service layer
- database models
- schemas/serializers
- simulator service
- trend ingestion service
- alarm evaluation service
- schedule service
- schedule-to-command evaluator (binds weekly JSON to output points)
- BACnet/simulator **write verification** worker (read-after-write, retry, mismatch detection)
- command/write service
- audit logging service
- auth/permission service
- tests

Frontend should include:
- login page
- main BAS shell layout
- navigation tree
- dashboard page
- equipment graphics page
- point detail drawer/page
- alarms page
- trends page
- schedules page
- admin/users page
- reports/export page
- settings/config page

Use a clean, professional UI. The interface should look like a real BAS workstation:
- left navigation tree
- top status bar
- main graphic/action pane
- alarm banner or alarm count indicator
- equipment cards
- point tables
- live values
- status colors
- trend charts
- schedule editor
- role-aware action buttons

Do not make the UI look like a generic SaaS dashboard only. It should clearly feel like a building automation operator workstation.

HEAD-END / SUPERVISORY GUI REQUIREMENTS

Implement the following supervisory GUI functions:

1. Login and role-based navigation
- User lands on a login page.
- Login requires username and password.
- After login, available navigation and actions depend on user role.
- ReadOnly users cannot command points, edit schedules, acknowledge alarms, or change setpoints.
- Operators can acknowledge alarms and make limited setpoint/schedule changes.
- Engineers/Admins can configure points, equipment, trends, alarms, schedules, and users.

2. Navigation tree
- Display a hierarchical navigation tree:
  Site → Building → Floor → Equipment → Points
- **Prefer** the richer BAS-typical tree described under *Supervisory navigation tree* (optional system/discipline and protocol-aware metadata) so the demo feels like a commercial head-end; the minimum path above remains valid for small sites.
- Clicking equipment opens its BAS graphic view.
- Clicking a point opens point detail/trend/history.
- Navigation tree should stay visible while the main pane changes.

3. BAS graphics
Create **template-driven** graphical equipment pages appropriate to the **building program** and **BACnet (or simulated) point model**—not only one HVAC archetype. Examples of programs: **VAV + central AHU**, **VRF + DOAS**, **HP DOAS**, **data center CRAH / chilled-water plant**, **lab** (ventilation / pressurization emphasis), **hospital** (isolation OR, critical zones), **lighting-forward** or mixed-use.

For the seeded demo, include at least:
- One **primary** air-side or plant synoptic (central AHU, DOAS, VRF header, CRAH row, etc.—whatever matches the template).
- One **terminal or zone** graphic (VAV, fan coil, VRF indoor unit, room summary, etc.).
- One **secondary or ancillary** view (lighting, exhaust, waterside, or a **generic** equipment graphic).

Each graphic should show:
- equipment name
- live point values
- command/status indicators
- alarm status
- setpoints
- animated or visually changing equipment status where practical
- red/green/yellow/gray BAS-style status colors
- active setpoint controls for authorized users
- link/buttons to properties, trends, schedules, and alarms

**Logic wire-sheet / flow graphic** (reference UX: `bas_build_spec/frontend_example/graphic.html`)

The reference HTML demonstrates a **logic-flow “wire sheet”** pattern that should be carried into the product (implemented in React or equivalent — **not** tied to Niagara RequireJS or BajaScript):

- **Horizontal flow strip:** a row of **nodes** (icon + short label + **live value**) connected by **arrows**, representing data or control flow (e.g. *Zone requests → AHU aggregation → Plant reset %*). Values update from the same realtime channel as the rest of the graphic.
- **Load / progress strips:** horizontal bars with percentage labels where a “% load” or reset signal improves situational awareness.
- **Operator feedback:** a **write / command log** (last N operations with ok/fail styling) and non-blocking toast or inline confirmation — same mental model as the reference’s control panel, adapted to this app’s audit trail.
- **Binding discovery affordance:** the reference probes slot names and shows a modal table; the product equivalent is **point / BACnet object discovery** (from seeded metadata or live driver) so engineers can align **display names** with **object identifiers**.

**Scenario — networked outside air temperature (OAT)** (building-agnostic; **per-site configuration**)

Many BACnet jobs include a **physical or supervisory OAT source** and one or more **controllers that do not have their own OAT sensor** but expect a **networked / shared OAT** value written from the head-end or from another controller. The product must support this pattern **without hardcoding any device address, instance number, or object ID** in code or in global acceptance checklists.

- **Source (configured):** the authoritative OAT — e.g. an **Analog Input** on a rooftop controller, an **Analog Value** maintained by the front end, or a validated weather feed mapped to a point.
- **Consumer (configured):** the writable point the field strategy reads — commonly a BACnet **Analog Value** `Present_Value` on the same or a **different** controller (object type and instance come from **discovery, import, or commissioning data** for that building only).
- **Operator naming:** projects use varying labels — e.g. **“OAT Networked”**, **“Network OAT”**, **“Outside Air Temp — Network”**, **“OA Temp Net”**. The demo seed should use **one clear pair** of display names (source vs networked) documented in site metadata; acceptance is by **role and binding**, not by a fixed string match across all buildings.
- **SupervisoryLink** (or equivalent) in seed/config and on the **logic wire-sheet**: *Authoritative OAT → supervisory fan-out service → networked OAT consumer* with live values on each node.
- **Writes:** same **safe command** policy as elsewhere (audit, permissions, confirmation where operator-initiated; automated links may use a system principal — document both). Rate limits, deadband, and BACnet **write priority** are **site-tunable**.

Illustrative wire-only examples (BACnet integration testing) may appear in **`bacnet_scripts.md`** or lab notes; they are **not** normative device assignments for the product.

**Example** — classic central AHU (when that template is selected); other templates swap in BACnet-appropriate points:

AHU graphic example points:
- Supply Fan Command
- Supply Fan Status
- Supply Fan Speed %
- Supply Air Temperature
- Supply Air Temperature Setpoint
- Return Air Temperature
- Mixed Air Temperature
- Outside Air Temperature
- Cooling Valve %
- Heating Valve %
- Outside Air Damper %
- Duct Static Pressure
- Duct Static Pressure Setpoint
- Occupancy Mode
- Alarm Status

**Example** — VAV-style terminal (when that template is selected):

VAV graphic example points:
- Space Temperature
- Space Temperature Setpoint
- Damper Position
- Airflow CFM
- Airflow Setpoint
- Reheat Valve %
- Occupancy Mode
- Discharge Air Temperature
- Alarm Status

4. Properties view
For each equipment and point, provide a properties page/drawer showing:
- name
- description
- units
- present value
- point type
- object type/object instance if applicable
- source protocol/address
- trend enabled
- alarm enabled
- commandable status
- last update timestamp
- communication status
- quality/status flags

Authorized users should be able to edit safe metadata fields such as display name, description, trend enable, alarm enable, and display units. Dangerous edits such as protocol address/object instance should be restricted to Admin/Engineer.

5. Safe command and setpoint workflow
Implement command/write simulation for commandable points.

The workflow must:
- require appropriate user role
- require confirmation before write
- require a reason/comment for write
- write at a configurable BACnet-style priority
- support release/relinquish command
- record the full command in the audit log
- show previous value, new value, user, timestamp, and result
- prevent writes to non-commandable points
- prevent ReadOnly users from writing
- clearly display when a point is overridden/commanded

Do not silently change values without an audit record.

6. Schedules
Implement a schedule editor with:
- weekly schedules
- separate daily schedules
- start/stop times
- exception schedules/holidays
- temporary override
- categories appropriate to the **building program** (examples: air-side occupancy, terminal/VRF, DOAS/ventilation, lighting, lab setback, clinical/OR—not limited to “AHU”/“VAV” labels)
- view/edit permissions
- audit logging of schedule changes

**Schedule UI (authoritative reference):** **`bas_build_spec/frontend_example/schedule_example.html`**

- Treat this file as the **canonical weekly run-schedule widget**: React-based **7-day × 24-hour** grid, **15-minute snap**, **draggable and resizable** occupied/run blocks, day-row hover, toolbar actions, and a **JSON preview** of the weekly model.
- The shipped product must implement the **same operator affordances and visual system** in a **production React + TypeScript** SPA (replace CDN `react`/`babel-standalone` with a normal bundle; keep behavior equivalent).
- **Extend the same `:root` tokens, Inter/system typography, card and panel chrome** across the **entire head-end UI** (navigation shell, tables, dialogs, alarms, trends, settings) so the application reads as **one coherent design** — not a mix of unrelated SaaS themes.

**Schedules driving BACnet motor / fan / pump (and similar) outputs**

- Internal representation remains **clean JSON** mappable later to BACnet **Schedule** objects.
- A **scheduler service** evaluates active intervals and produces **desired command states** for **bound supervisory outputs** (fans, pumps, enable contacts, etc.).
- A **BACnet or simulator driver** performs **WriteProperty** (or priority-array writes) on **command points**. Until commissioning imports real object lists, the implementation may use **documented heuristics** (e.g. names containing `FAN`, `SUPPLY`, `VFD`, `PUMP`, `RUN`, `CMD` paired with `STATUS`, `PROOF`, `RUNNING`, `FBK`) — **must** be overridable via **configuration/seed** without code edits.
- **Read-after-write verification:** after each command write, the driver (or a dedicated **verification worker**) **poll-reads** the associated **feedback / status / proof** points within a configurable window; if **command ≠ feedback** beyond debounce/tolerance, raise a **command/status mismatch** alarm and show **mismatch state** on the schedule or equipment context panel.
- **Retries:** on comm failure, timeout, or rejected write, **retry with exponential backoff** up to configured limits, with **audit** and **non-spam** logging; give up into a **failed command** / alarm state if limits exceeded.
- **UI feedback:** operators see **last command**, **last verified feedback**, **match / mismatch / pending verify**, and **retry count** for each bound motor output where practical.

Represent the schedule internally in a clean JSON structure that could later map to BACnet Schedule objects.

The UI should allow:
- view schedule
- edit schedule
- add exception date
- remove exception date
- enable/disable schedule
- apply schedule to equipment or point
- show currently active/inactive status

7. Trends
Implement trend collection and viewing.

Requirements:
- Any analog or binary point can be trended.
- Trend data can be generated by the simulator.
- Trend page can graph multiple points.
- User can select date range.
- User can zoom/pan if chart library supports it.
- User can inspect numeric values.
- User can export selected trend data to CSV.
- Trend data includes timestamp, value, and quality/status.
- Long-term storage should be designed for future 2-year retention even if the demo uses a smaller generated dataset.
- Trend intervals should be configurable per point.

8. Alarms
Implement an alarm system with:
- binary alarms
- analog high/low alarms on **BACnet temperature (and other analog) sensors** mapped as supervisory points — limits configurable per point; hysteresis recommended
- communication alarms
- stale data alarms
- command/status mismatch alarms
- alarm severity
- alarm state: active, acknowledged, returned_to_normal, shelved
- alarm history log
- alarm acknowledgement
- alarm shelving
- operator instruction/message field
- real-time alarm updates in UI

Alarm page should support:
- active alarms
- alarm history
- filtering by building/equipment/severity/state
- acknowledge selected alarm
- shelve selected alarm
- sort by time/severity/equipment
- link from alarm to equipment graphic
- show alarm lifecycle timestamps

9. Events and audit logging
The system must log:
- user login
- failed login
- logout if practical
- point command/write
- point release
- schedule edit
- alarm acknowledgement
- alarm shelving
- metadata/config edit
- user/role changes

Audit log page should support:
- filtering by user/action/time/equipment
- CSV export
- read-only display for operators
- admin visibility into all audit records

10. Realtime updates
Use WebSockets, SSE, or polling to update:
- point present values
- equipment status
- alarms
- navigation status counts if practical
- **schedule command verification state** (pending verify, matched, mismatch, retrying) for bound motor outputs

The UI should not require manual page refresh to see changing point values.

**Polling vs push:** combine **event-driven** updates where possible with **interval polling** for BACnet reads used for **write verification**, **staleness**, **alarm evaluation**, and **historian ingestion** — intervals and backoff **configurable**; document defaults.

11. BAS simulator
Implement a simulator service that creates realistic data for:
- one site
- one building
- at least two floors
- at least one AHU
- at least four VAV boxes
- at least one chiller or boiler
- one pump
- one lighting panel

The simulator should:
- update point values periodically
- create reasonable HVAC behavior
- produce occasional alarms
- simulate stale/offline points
- simulate command/status mismatch
- simulate occupied/unoccupied mode
- create trend samples
- respect setpoint changes in a basic way

Examples:
- AHU supply air temp should move toward supply air setpoint.
- VAV space temp should vary slowly.
- Fan status should normally follow fan command, but occasionally fail to prove status for an alarm.
- Communication status can occasionally go offline for a simulated device.
- Lighting status can follow schedule.

12. Reporting and exports
Implement:
- export trend data to CSV
- export alarm history to CSV
- export audit log to CSV
- simple report page showing:
  - active alarms count
  - offline equipment count
  - overridden points count
  - stale points count
  - trended point count
  - recent commands

13. System status
Implement a system status page showing:
- database connection status
- simulator status
- realtime connection status
- number of active points
- number of active alarms
- number of stale points
- last simulator update timestamp

14. Documentation
Create documentation in README.md that includes:
- project purpose
- architecture overview
- technology stack
- how to run locally
- how to run with Docker Compose
- seeded demo credentials
- BAS concepts modeled
- API overview
- simulator overview
- user roles
- safety notes for future real BACnet integration
- testing commands
- known limitations

Include a docs folder if useful:
- docs/architecture.md
- docs/bas_domain_model.md
- docs/api.md
- docs/acceptance_criteria.md

SAFETY AND CONTROL REQUIREMENTS

This system is a prototype supervisory BAS application. The software must be designed safely.

Do not create uncontrolled real-world write behavior.

If a future real BACnet driver is included, it must be disabled by default and require explicit configuration. The default demo must use simulated data only.

All commands must:
- require authenticated user
- check role permissions
- validate target point is commandable
- require confirmation
- require reason/comment
- create audit log entry
- expose release/relinquish behavior
- clearly show overridden/commanded state

The UI should clearly distinguish:
- measured value
- setpoint
- command
- status/proof
- alarm state
- communication state
- stale data state
- overridden state
- disabled point
- fault point

DESIGN STYLE

**Primary shell + schedules (authoritative for most of the SPA):** **`bas_build_spec/frontend_example/schedule_example.html`**

- Use its **`:root` tokens** (`--bg`, `--panel`, `--line`, `--text`, `--muted`, `--accent`, `--block`, `--danger`, `--green`), **Inter / system-ui typography**, **rounded cards**, **toolbar density**, and **status semantics** (primary actions, danger, success) as the **default head-end theme** for **navigation, forms, lists, alarms, trends, settings, and the weekly schedule editor**.
- Implement the schedule editor as a **production React + TypeScript** module that **matches the demo’s behaviors** (snap, drag, resize, weekly JSON model); do not ship CDN `babel-standalone` in production.

**Synoptic / plant graphics and logic-flow (secondary reference):** **`bas_build_spec/frontend_example/graphic.html`**

- Reuse its **layout patterns** (logic-flow strip, gauge bars, plant headers, BAS status color **meanings**) for **equipment synoptics and wire-sheet strips** — either **embed** those views inside the schedule shell as darker “graphic panes” **or** re-map the same green/red/yellow/cyan meanings onto schedule-token surfaces so status stays familiar.
- Do not copy Niagara-specific script APIs; only **UX and density** carry over.

Make the UI clean and professional:
- **Coherent** with **`schedule_example.html`** for chrome; **BAS-literate** status colors (map green/red/yellow/gray/cyan heat–cool semantics from `graphic.html` into tokens or component variants).
- BAS-style navigation tree inside the shell
- equipment graphics that read like simple mechanical schematics (see § BAS graphics)
- avoid clutter
- use tables where operators need dense point lists
- use cards where summary status is useful
- make it usable on desktop first

DELIVERABLES

When finished, the repository must include:

1. Backend application
2. Frontend application
3. Database migrations or schema setup
4. Seed/demo data
5. BAS simulator
6. Docker Compose file
7. README with run instructions
8. Tests
9. Acceptance criteria document (`acceptance_criteria.md`)
10. Screenshots or notes describing major screens if screenshot automation is practical

CODEX / AGENT IMPLEMENTATION PACK (schedules + BACnet motors + verification)

For **Codex CLI** (and other coding agents) implementing this slice **without overfitting one job**, follow **`bas_build_spec/skills/bacnet-schedule-motor-verify/SKILL.md`**. That skill is **normative guidance** for: React schedule widget parity, heuristic motor bindings, write → read-verify → retry, mismatch and temperature alarms, and polling/data mechanisms. Agents may add supporting modules, migrations, or tests **as long as** behavior satisfies **`acceptance_criteria.md`** and the relevant sections of this spec.

MINIMUM API ENDPOINTS

Implement REST endpoints or equivalent for:

Auth:
- POST /auth/login
- POST /auth/logout or token invalidation if applicable
- GET /auth/me

Sites/buildings/equipment:
- GET /sites
- GET /buildings
- GET /floors
- GET /equipment
- GET /equipment/{id}
- GET /equipment/{id}/points
- GET /equipment/{id}/alarms
- GET /equipment/{id}/trends

Points:
- GET /points
- GET /points/{id}
- PATCH /points/{id}
- POST /points/{id}/command
- POST /points/{id}/release
- GET /points/{id}/trend

Trends:
- GET /trends
- GET /trends/export.csv

Alarms:
- GET /alarms
- POST /alarms/{id}/acknowledge
- POST /alarms/{id}/shelve
- GET /alarms/history
- GET /alarms/export.csv

Schedules:
- GET /schedules
- POST /schedules
- GET /schedules/{id}
- PATCH /schedules/{id}
- DELETE /schedules/{id}
- POST /schedules/{id}/exceptions

Audit:
- GET /audit
- GET /audit/export.csv

System:
- GET /system/status

Realtime:
- /ws or /events for point and alarm updates

ACCEPTANCE CRITERIA

Acceptance criteria document: **`acceptance_criteria.md`**. Codex/cron automation handoff: **`BUILD_CHECKPOINTS.md`** and **`cron_codex/README.md`** (optional: auto-remove cron when acceptance is complete per `cron_codex/bin/check_acceptance_complete.sh` and `REMOVE_CRON_WHEN_COMPLETE`; **`POST_WAKE_HOOK`** to restart the live stack; dev servers listen on **`0.0.0.0`** for remote dial-in per README). Agent skill taxonomy (repo-local, Codex-style): **`bas_build_spec/skills/`** (see **`bas_build_spec/skills/README.md`**); Cursor uses symlinks under **`~/.cursor/skills/`** via **`cron_codex/bin/bas_skills_link.sh`**.

The project is complete only when all of the following are true.

General build criteria:
- The application starts locally using documented commands.
- The application starts with Docker Compose using documented commands.
- The database initializes successfully.
- Demo data is seeded automatically or with a documented command.
- A user can log in with documented demo credentials.
- The app can run without real BACnet hardware.

Architecture criteria:
- Backend and frontend are separated cleanly.
- Domain models exist for site, building, floor, equipment, point, trend sample, alarm, schedule, user/role, and audit log.
- Business logic is not all jammed into API route handlers.
- Simulator logic is separated from API logic.
- Command/write logic is centralized and audited.
- Configuration is handled through environment variables where appropriate.
- Secrets are not hardcoded.

Navigation/UI criteria:
- Login page works.
- Main BAS layout has a navigation tree and main action pane.
- User can navigate Site → Building → Floor → Equipment → Points.
- Where implemented: navigation also supports at least one **BAS-typical** grouping (e.g. System/discipline or protocol/device metadata view) consistent with *Supervisory navigation tree* in the domain section.
- Equipment pages show live point values.
- The UI has obvious BAS-style status colors.
- The UI shows active alarm count or alarm indicator.
- The UI is usable on desktop browser without developer tools.

Graphics criteria (building program + BACnet; see **`acceptance_criteria.md`** § Graphics):
- Multiple **HVAC / facility archetypes** can be represented (e.g. VAV + AHU, VRF + DOAS, HP DOAS, data-center CRAH/plant, lab, hospital, lighting-heavy)—graphics and seeded points follow the **configured template**, not a single fixed “AHU + VAV only” story.
- At least one **primary** plant or air-side synoptic appropriate to the template; at least one **terminal/zone** view; at least one **secondary/ancillary** system view (or generic equipment page) when the program warrants it.
- At least one graphic includes a **logic wire-sheet** strip (nodes + arrows + live values) for a documented control or data flow (see spec § BAS graphics — logic wire-sheet).
- The seeded demo documents a **networked OAT** (or equivalent **SupervisoryLink**) story: source point → supervisory path → **configured consumer** point (commonly a BACnet **Analog Value** on the same or another controller), with simulator or live data per driver mode — **no hardcoded BACnet device IDs, IPs, or object instances** in application defaults; those are supplied only by **per-building** configuration or discovery.
- Live values update without a full page refresh.
- Graphics include links/buttons for properties, trends, schedules, and alarms.
- Authorized users can initiate setpoint/command workflow from the graphic.

Point/property criteria:
- Point list page exists.
- Point detail view exists.
- Point properties display value, units, type, source, status, last update, trend setting, alarm setting, and commandable state.
- Editable metadata can be changed only by authorized roles.
- Point status clearly shows normal, alarm, stale, offline, overridden, disabled, or fault where applicable.

Command/write criteria:
- ReadOnly user cannot command points.
- Operator or Engineer can command only commandable points.
- Command workflow requires confirmation.
- Command workflow requires reason/comment.
- Command writes are recorded in audit log.
- Release/relinquish command exists.
- Non-commandable point write attempt is rejected.
- Commanded/overridden state is visible in UI.

Schedule criteria:
- Schedule list page exists.
- Weekly schedule editor exists and **matches the interaction and styling** of **`frontend_example/schedule_example.html`** (7-day grid, snap, drag/resize blocks, JSON model), implemented as production React/TS.
- Exception schedule editor exists.
- Schedule categories exist appropriate to the **building program** (at least four distinct buckets—e.g. air-side occupancy, terminal/VRF, DOAS/ventilation, lighting, lab, or clinical—not necessarily named AHU/VAV).
- Schedule changes are saved.
- Schedule changes are audited.
- Unauthorized users cannot edit schedules.
- Current active/inactive schedule status is visible.
- **Motor / fan / pump (and similar) outputs** bound to the schedule are driven via the **BACnet or simulator driver** with **read-after-write verification**, **retries**, and **command/status mismatch** indication when feedback does not match command within policy.
- Operators can see **verification / mismatch / retry** state for those bindings where practical (schedule context or linked equipment strip).

Trend criteria:
- Trends page exists.
- At least 10 points are trended in demo data.
- Historical samples are **persisted** in the configured time-series store (not only held in RAM for the current session) for points marked historized/trended, per *Telemetry ingestion and time-series storage*.
- User can select one or more points to graph.
- User can select date/time range.
- Trend chart displays historical values.
- Trend data can export to CSV.
- Trend samples include timestamp, value, and quality/status.
- Trend intervals are configurable or represented in the data model.

Alarm criteria:
- Alarm page exists.
- Active alarm list exists.
- Alarm history exists.
- Analog high/low alarms are supported, including on **BACnet-mapped temperature** (and other analog sensor) points with configurable limits.
- Binary alarm state is supported.
- Stale/offline/communication alarm is supported.
- Command/status mismatch alarm is supported (including **schedule-driven motor** command vs feedback mismatch surfaced in UI).
- User can acknowledge alarm if authorized.
- User can shelve alarm if authorized.
- Alarm lifecycle timestamps are stored.
- Alarm history export to CSV works.
- Clicking an alarm can take user to related equipment or point.

Audit criteria:
- Login attempts are logged.
- Point commands are logged.
- Point releases are logged.
- Schedule edits are logged.
- Alarm acknowledgements are logged.
- Alarm shelving is logged.
- Configuration edits are logged.
- Audit log can be filtered.
- Audit log can be exported to CSV.

Security criteria:
- Authentication is required for app access.
- Passwords are not stored in plaintext.
- Role-based permissions are enforced on backend, not just hidden in frontend.
- Unauthorized API calls are rejected.
- Command/write endpoints enforce permissions server-side.
- Dangerous operations require proper role.
- Basic input validation exists.
- CORS/config defaults are reasonable for local development.

Simulator criteria:
- Simulator creates realistic changing point values.
- Simulator produces trend samples.
- Simulator occasionally produces alarms.
- Simulator can simulate offline/stale equipment.
- Simulator can simulate command/status mismatch.
- Simulator responds reasonably to setpoint changes.
- Simulator can be started/stopped/configured through environment or documented command.

Reporting criteria:
- Summary report page exists.
- Active alarms count is shown.
- Offline equipment count is shown.
- Overridden points count is shown.
- Stale points count is shown.
- Recent command activity is shown.
- CSV exports work for trends, alarms, and audit logs.

Testing criteria:
- Backend tests cover auth, permissions, point commands, alarms, schedules, and audit logging.
- Frontend or end-to-end tests cover login, navigation, alarm acknowledgement, schedule edit, and command workflow where practical.
- Tests can be run with a documented command.
- Linting or formatting command is documented.
- No failing tests are left unexplained.

Documentation criteria:
- README explains what the BAS app does.
- README explains how to run locally.
- README explains how to run with Docker Compose.
- README lists demo users and roles.
- README explains simulator behavior.
- README explains safety assumptions.
- README explains future real BACnet integration path.
- Acceptance criteria document is included; implementation status tracked honestly (e.g. in `BUILD_CHECKPOINTS.md` or release notes).

FINAL OUTPUT REQUIRED FROM AGENT

At the end of the build, provide:

1. A short summary of what was built.
2. The exact commands to run the app.
3. The exact commands to run tests.
4. Demo login credentials.
5. A list of major files/directories created.
6. Any incomplete acceptance criteria.
7. Any known limitations.
8. Any safety warnings related to real BAS/BACnet integration.

Do not claim the project is complete unless the acceptance criteria are actually met.
Do not skip tests.
Do not hardcode secrets.
Do not require real BAS hardware.
Build a professional BAS head-end prototype that a controls engineer, commissioning agent, or facility operator would recognize as credible.