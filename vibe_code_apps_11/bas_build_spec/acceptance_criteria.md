# BAS head-end — acceptance criteria

This document mirrors `spec.md` (§ Acceptance criteria). Use it for tickets, CI gates, and incremental Codex runs. Track verification in `BUILD_CHECKPOINTS.md`, release notes, or your issue tracker—there are **no** Markdown checkboxes here.

**Related:** `BUILD_CHECKPOINTS.md` (incremental wake status), `cron_codex/README.md` (scheduled Codex runner).

---

## Scope (this phase)

- **Architectural floor plans** (CAD underlays, plan graphics, click-from-plan navigation) are **not** required.
- Navigation and demos may use **Site → Building → Equipment → Points** without an intermediate floor or plan layer unless you add one later.

## General build

- Application starts locally using documented commands
- Application starts with Docker Compose using documented commands
- Database initializes successfully
- Demo data is seeded automatically or with a documented command
- User can log in with documented demo credentials
- App runs without real BACnet hardware

## Architecture

- Backend and frontend separated cleanly
- Domain models: site, building, equipment, point, trend sample, alarm, schedule, user/role, audit log (optional **floor/level** entity only if useful—**not** tied to floor-plan graphics)
- Business logic not confined to route handlers
- Simulator separated from API logic
- Command/write logic centralized and audited
- Configuration via environment variables where appropriate
- No hardcoded secrets

## Navigation / UI

- Login page works
- Main BAS layout: navigation tree + main pane
- Navigate Site → Building → Equipment → Points
- **BAS-typical tree:** at least one extra grouping or facet beyond the minimum path (e.g. System/discipline node, or equipment grouped by **protocol / device identity** metadata the site configures) per `spec.md` *Supervisory navigation tree*
- Equipment pages show live point values
- BAS-style status colors (green/red/yellow/gray semantics)
- Visual theme: **shell, schedules, forms, and dense tables** align with **`bas_build_spec/frontend_example/schedule_example.html`** (`:root` tokens, Inter/system typography, cards); **synoptic / wire-sheet** views may use **`graphic.html`**-style density and BAS status color semantics per spec § DESIGN STYLE
- Active alarm count or indicator visible
- Usable on desktop without developer tools

## Graphics (building program + BACnet, not one HVAC archetype)

Graphics must reflect **whatever HVAC / facility archetype** the site is configured for—driven by **equipment + BACnet (or simulator) points**, not a hardcoded “only AHU + VAV” assumption.

- **Building-program templates:** documented way to represent multiple archetypes (examples: **VAV + central AHU**, **VRF + DOAS**, **HP DOAS**, **data center CRAH / CHW**, **lab** ACH or pressurization context, **hospital** isolation OR / critical zones, **lighting-only** or mixed-use). Seeded or config-driven **equipment + point sets** match the chosen template(s) for the demo site.
- **Primary HVAC / plant graphic(s):** at least one synoptic for the site’s *primary* plant or air side (e.g. central plant, DOAS, VRF header, CRAH row—whatever the template defines) with **live BACnet-backed or simulated** points appropriate to that type.
- **Terminal / zone graphic:** at least one graphic for a **representative terminal or zone** (e.g. VAV box, VRF indoor unit, fan coil, room/zone summary) appropriate to the template—not necessarily “VAV” in the name if the building is VRF + DOAS.
- **Secondary / ancillary graphic:** at least one additional system view when the program warrants it (e.g. lighting, exhaust, reheat, waterside, or a **generic** equipment page) so multi-system campuses are representable.
- Live values update **without full page refresh** (SSE/WebSocket or equivalent).
- Graphics **deep-link** to properties, trends, schedules, and alarms for the equipment/points shown.
- **Authorized users** can start the **safe setpoint/command** workflow from a graphic (same rules as Command/write section).
- **Logic wire-sheet strip:** at least one equipment or plant graphic includes a **horizontal flow** (nodes with labels + **live values** + arrows) for a documented data/control path, in the spirit of `frontend_example/graphic.html` (`.flow-section` / `.flow-node` pattern) — stack-agnostic, no Niagara coupling.
- **Networked OAT (config-driven):** documented **SupervisoryLink** (or equivalent binding) from an **authoritative outside-air temperature** source point to a **networked OAT** consumer the site defines — e.g. a point whose **display name** matches project convention such as **“OAT Networked”**, **“Network OAT”**, or **“Outside Air Temp — Network”** (exact string is **site configuration**, not hardcoded in these criteria). No acceptance criterion may require a **specific BACnet device ID, IP, or object instance**; those come only from **per-building** discovery or import. Demo may use **simulator** values until a real driver is enabled; the **logic wire-sheet** shows the flow with live values from whatever source is configured.

## Telemetry (database)

- Historized / trend-eligible point samples are **written to the configured TSDB** (or Timescale-backed store), not kept only in process memory, per `spec.md` *Telemetry ingestion and time-series storage*
- Trend charts and exports read from that persistence path (or a documented query layer over it)

## Points / properties

- Point list page
- Point detail view
- Properties show value, units, type, source, status, last update, trend/alarm flags, commandable state
- Metadata edits restricted by role
- Status shows normal, alarm, stale, offline, overridden, disabled, fault as applicable

## Command / write

- ReadOnly cannot command
- Operator/Engineer: commandable points only
- Confirmation required before write
- Reason/comment required
- Commands in audit log
- Release/relinquish exists
- Non-commandable writes rejected
- Commanded/overridden state visible

## Schedules

- Schedule list page
- Weekly schedule editor: **same core UX as** **`frontend_example/schedule_example.html`** (7-day × 24h grid, 15-minute snap, drag/resize blocks, weekly JSON model), shipped as **production React/TypeScript** (not CDN Babel demo wiring)
- Exception schedule editor
- Schedule categories are **appropriate to the building program** (examples: air-side occupancy, terminal/VRF modes, DOAS/ventilation, lighting, lab setback, OR isolation—at least **four** distinct category buckets documented for the demo site; names need not be “AHU”/“VAV”)
- Changes persisted and audited
- Unauthorized users blocked from edits
- Active/inactive schedule status visible
- **Schedule → motor (or fan/pump) outputs:** documented bindings from schedule intervals to **command points**; driver performs writes; **heuristic or config-guessed** BACnet point roles are acceptable until commissioning overrides
- **Read-after-write verification:** after motor-related writes, system **poll-reads feedback** on an interval, **retries** on failure, and surfaces **match / mismatch / pending** in UI; persistent mismatch raises **command/status mismatch** alarm
- **Codex skill:** implementers follow **`bas_build_spec/skills/bacnet-schedule-motor-verify/SKILL.md`** for generic robustness

## BACnet driver / polling (motor verification)

- **Polling and/or COV-style** read paths documented for verification, staleness, alarm evaluation, and historian samples (intervals configurable)
- Simulator can demonstrate **failed write**, **wrong feedback**, and **retry** without real field hardware

## Trends

- Trends page
- At least 10 trended points in demo data
- Multi-point graph, date range selection
- Chart shows historical values
- CSV export
- Samples include timestamp, value, quality/status
- Intervals configurable or modeled

## Alarms

- Alarm page, active list, history
- Analog high/low on **BACnet-backed (or simulated) temperature and other sensor points** where configured, binary, stale/offline/comm, command/status mismatch (including **schedule motor** command vs feedback)
- Acknowledge and shelve (authorized)
- Lifecycle timestamps stored
- Alarm history CSV export
- Navigation from alarm to equipment/point

## Audit

- Login success/failure logged
- Point commands/releases logged
- Schedule edits logged
- Alarm ack/shelve logged
- Config edits logged
- Audit filterable and CSV export

## Security

- Auth required for app access
- Passwords not stored plaintext
- RBAC enforced on backend
- Unauthorized API calls rejected
- Command endpoints enforce permissions server-side
- Dangerous operations require proper role
- Basic input validation
- Reasonable CORS/defaults for local dev

## Simulator

- Realistic changing values
- Trend samples produced
- Occasional alarms
- Offline/stale simulation
- Command/status mismatch simulation
- Responds to setpoint changes
- Start/stop/config via env or documented command

## Reporting

- Summary report page
- Counts: active alarms, offline equipment, overridden points, stale points, recent commands
- CSV exports: trends, alarms, audit

## Testing

- Backend tests: auth, permissions, commands, alarms, schedules, audit
- Frontend or E2E: login, navigation, alarm ack, schedule edit, command flow (where practical)
- Documented test command; no unexplained failing tests
- Lint/format documented

## Documentation

- README: purpose, local run, Compose, demo users, simulator, safety, future BACnet path
- Implementation status against these criteria is documented (e.g. in `BUILD_CHECKPOINTS.md` or release notes)

---

## Release gate (stability before last sign-off & cron removal)

Use this block as the **honest bar** before treating the product as release-ready and letting automation remove cron (`REMOVE_CRON_WHEN_COMPLETE=true`). **You or CI** should verify each line below—not assumed from a quick pass.

- **Backend HTTP smoke:** Documented `curl -sfS` (or `wget -qO-`) commands return **HTTP 200** for at least: **`/health`** (or equivalent), **one public demo API** (e.g. site/building tree or `/api/demo/site`), and **one authenticated API** using the documented demo token or login+cookie flow.
- **Backend / process logs:** Cold start per README (or `docker compose up` then wait N seconds) shows **no unhandled exception tracebacks** in backend logs during that window; the smoke URLs above return **no 5xx**.
- **Frontend build:** Documented **`npm run build`** (or `pnpm`/`yarn` equivalent) or documented **frontend Docker image build** completes with **zero errors** (warnings acceptable if listed as known).
- **Frontend sweep (console-clean):** Documented **manual steps** or **Playwright (or other E2E)** covering: login → navigate **Site → Building → Equipment → Points** → open one point or equipment view → confirm **simulator-backed** values render. **Browser devtools console** must show **no `error` level** messages on that path (document any allowed benign warnings).
- **BACnet vs simulator:** Default runtime uses **simulator/mock** data paths only; **real BACnet/IP (Who-Is / I-Am discovery, BBMD, writes to field devices)** is **off or unreachable** unless a **separately documented** lab flag + `bacnet_scripts.md` bind-address procedure is enabled. **Scheduled Codex wakes must not run BACnet wire discovery** unless an explicit checkpoint calls for lab-only work **and** you accept network traffic risk.
- **End-to-end data sweep:** Documented one-shot script or README subsection: sequential calls (or UI clicks mirrored by API) proving **site → building → equipment → points** return **expected seeded IDs and non-empty payloads** with **no 4xx/5xx** on the happy path.

Optional automation: set **`BAS_SMOKE_GET_URLS`** in `cron_codex/.env` (space-separated GET URLs) and run **`cron_codex/bin/bas_smoke.sh`** after the app is up; it will `curl` each URL when the variable is non-empty.

---

## Final delivery (from spec)

When the project is “done,” also capture:

1. Short summary of what was built  
2. Exact run commands  
3. Exact test commands  
4. Demo credentials  
5. Major files/directories created  
6. Any incomplete criteria  
7. Known limitations  
8. Safety warnings for real BACnet integration  

Do **not** claim completion until the **release gate** and other criteria above are **actually verified**, not assumed.
