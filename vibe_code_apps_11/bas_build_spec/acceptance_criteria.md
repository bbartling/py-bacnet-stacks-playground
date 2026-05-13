# BAS head-end — acceptance criteria (checklist)

This checklist mirrors `spec.md` (§ Acceptance criteria). Use it for tickets, CI gates, and incremental Codex runs. Check items only when they are **verified** in a running build.

**Related:** `BUILD_CHECKPOINTS.md` (incremental wake status), `cron_codex/README.md` (scheduled Codex runner).

---

## General build

- [x] Application starts locally using documented commands
- [ ] Application starts with Docker Compose using documented commands
- [ ] Database initializes successfully
- [x] Demo data is seeded automatically or with a documented command
- [x] User can log in with documented demo credentials
- [x] App runs without real BACnet hardware

## Architecture

- [x] Backend and frontend separated cleanly
- [ ] Domain models: site, building, floor, equipment, point, trend sample, alarm, schedule, user/role, audit log
- [ ] Business logic not confined to route handlers
- [x] Simulator separated from API logic
- [x] Command/write logic centralized and audited
- [x] Configuration via environment variables where appropriate
- [x] No hardcoded secrets

## Navigation / UI

- [ ] Login page works
- [x] Main BAS layout: navigation tree + main pane
- [x] Navigate Site → Building → Floor → Equipment → Points
- [ ] Equipment pages show live point values
- [x] BAS-style status colors (green/red/yellow/gray semantics)
- [x] Visual theme (colors, dark surfaces, card chrome, typography) matches the intent of **`bas_build_spec/frontend_example/graphic.html`** / spec § DESIGN STYLE
- [x] Active alarm count or indicator visible
- [ ] Usable on desktop without developer tools

## Graphics (building program + BACnet, not one HVAC archetype)

Graphics must reflect **whatever HVAC / facility archetype** the site is configured for—driven by **equipment + BACnet (or simulator) points**, not a hardcoded “only AHU + VAV” assumption.

- [ ] **Building-program templates:** documented way to represent multiple archetypes (examples: **VAV + central AHU**, **VRF + DOAS**, **HP DOAS**, **data center CRAH / CHW**, **lab** ACH or pressurization context, **hospital** isolation OR / critical zones, **lighting-only** or mixed-use). Seeded or config-driven **equipment + point sets** match the chosen template(s) for the demo site.
- [ ] **Primary HVAC / plant graphic(s):** at least one synoptic for the site’s *primary* plant or air side (e.g. central plant, DOAS, VRF header, CRAH row—whatever the template defines) with **live BACnet-backed or simulated** points appropriate to that type.
- [ ] **Terminal / zone graphic:** at least one graphic for a **representative terminal or zone** (e.g. VAV box, VRF indoor unit, fan coil, room/zone summary) appropriate to the template—not necessarily “VAV” in the name if the building is VRF + DOAS.
- [ ] **Secondary / ancillary graphic:** at least one additional system view when the program warrants it (e.g. lighting, exhaust, reheat, waterside, or a **generic** equipment page) so multi-system campuses are representable.
- [ ] Live values update **without full page refresh** (SSE/WebSocket or equivalent).
- [ ] Graphics **deep-link** to properties, trends, schedules, and alarms for the equipment/points shown.
- [ ] **Authorized users** can start the **safe setpoint/command** workflow from a graphic (same rules as Command/write section).

## Points / properties

- [x] Point list page
- [x] Point detail view
- [x] Properties show value, units, type, source, status, last update, trend/alarm flags, commandable state
- [ ] Metadata edits restricted by role
- [ ] Status shows normal, alarm, stale, offline, overridden, disabled, fault as applicable

## Command / write

- [x] ReadOnly cannot command
- [x] Operator/Engineer: commandable points only
- [x] Confirmation required before write
- [x] Reason/comment required
- [x] Commands in audit log
- [x] Release/relinquish exists
- [x] Non-commandable writes rejected
- [x] Commanded/overridden state visible

## Schedules

- [x] Schedule list page
- [ ] Weekly schedule editor
- [ ] Exception schedule editor
- [x] Schedule categories are **appropriate to the building program** (examples: air-side occupancy, terminal/VRF modes, DOAS/ventilation, lighting, lab setback, OR isolation—at least **four** distinct category buckets documented for the demo site; names need not be “AHU”/“VAV”)
- [x] Changes persisted and audited
- [x] Unauthorized users blocked from edits
- [x] Active/inactive schedule status visible

## Trends

- [ ] Trends page
- [x] At least 10 trended points in demo data
- [ ] Multi-point graph, date range selection
- [ ] Chart shows historical values
- [x] CSV export
- [x] Samples include timestamp, value, quality/status
- [ ] Intervals configurable or modeled

## Alarms

- [x] Alarm page, active list, history
- [x] Analog high/low, binary, stale/offline/comm, command/status mismatch
- [x] Acknowledge and shelve (authorized)
- [x] Lifecycle timestamps stored
- [x] Alarm history CSV export
- [x] Navigation from alarm to equipment/point

## Audit

- [x] Login success/failure logged
- [x] Point commands/releases logged
- [x] Schedule edits logged
- [x] Alarm ack/shelve logged
- [ ] Config edits logged
- [x] Audit filterable and CSV export

## Security

- [ ] Auth required for app access
- [x] Passwords not stored plaintext
- [x] RBAC enforced on backend
- [x] Unauthorized API calls rejected
- [x] Command endpoints enforce permissions server-side
- [x] Dangerous operations require proper role
- [x] Basic input validation
- [ ] Reasonable CORS/defaults for local dev

## Simulator

- [x] Realistic changing values
- [x] Trend samples produced
- [x] Occasional alarms
- [x] Offline/stale simulation
- [x] Command/status mismatch simulation
- [x] Responds to setpoint changes
- [ ] Start/stop/config via env or documented command

## Reporting

- [x] Summary report page
- [x] Counts: active alarms, offline equipment, overridden points, stale points, recent commands
- [x] CSV exports: trends, alarms, audit

## Testing

- [x] Backend tests: auth, permissions, commands, alarms, schedules, audit
- [ ] Frontend or E2E: login, navigation, alarm ack, schedule edit, command flow (where practical)
- [x] Documented test command; no unexplained failing tests
- [ ] Lint/format documented

## Documentation

- [ ] README: purpose, local run, Compose, demo users, simulator, safety, future BACnet path
- [x] Acceptance criteria honestly marked complete/incomplete

---

## Release gate (stability before last sign-off & cron removal)

Use this block as the **honest bar** before marking the whole checklist complete and letting automation remove cron (`REMOVE_CRON_WHEN_COMPLETE=true`). Only check `[x]` after **you or CI** has verified — not because the model “thinks” it passes.

- [x] **Backend HTTP smoke:** Documented `curl -sfS` (or `wget -qO-`) commands return **HTTP 200** for at least: **`/health`** (or equivalent), **one public demo API** (e.g. site/building tree or `/api/demo/site`), and **one authenticated API** using the documented demo token or login+cookie flow.
- [x] **Demo auth smoke (curl):** From localhost or LAN, `POST` the documented login route with each **seeded demo user** in `bas_app/README.md` returns **200** and the documented **role** + token field; wrong password returns **401**; **ReadOnly** cannot perform protected writes (e.g. schedule or command **403**). Sync `cron_codex/demo_auth.env` from README, then run **`cron_codex/bin/bas_smoke_login.sh`**. Cursor: verify only (`skills/spec-validation/`); do not edit `bas_app/` to pass this gate.
- [x] **Backend / process logs:** Cold start per README (or `docker compose up` then wait N seconds) shows **no unhandled exception tracebacks** in backend logs during that window; the smoke URLs above return **no 5xx**.
- [x] **Frontend build:** Documented **`npm run build`** (or `pnpm`/`yarn` equivalent) or documented **frontend Docker image build** completes with **zero errors** (warnings acceptable if listed as known).
- [ ] **Frontend sweep (console-clean):** Documented **manual steps** or **Playwright (or other E2E)** covering: login → navigate **Site → Building → Floor → Equipment → Points** → open one point or equipment view → confirm **simulator-backed** values render. **Browser devtools console** must show **no `error` level** messages on that path (document any allowed benign warnings).
- [x] **BACnet vs simulator:** Default runtime uses **simulator/mock** data paths only; **real BACnet/IP (Who-Is / I-Am discovery, BBMD, writes to field devices)** is **off or unreachable** unless a **separately documented** lab flag + `bacnet_scripts.md` bind-address procedure is enabled. **Scheduled Codex wakes must not run BACnet wire discovery** unless an explicit checkpoint calls for lab-only work **and** you accept network traffic risk.
- [x] **End-to-end data sweep:** Documented one-shot script or README subsection: sequential calls (or UI clicks mirrored by API) proving **site → building → floor → equipment → points** return **expected seeded IDs and non-empty payloads** with **no 4xx/5xx** on the happy path.

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

Do **not** claim completion until the checked items above are actually satisfied.
