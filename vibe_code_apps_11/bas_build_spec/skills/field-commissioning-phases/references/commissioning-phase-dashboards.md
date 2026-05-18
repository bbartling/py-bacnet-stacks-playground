# Commissioning phase dashboards — routes, gates, and UX contract

Use with **`field-commissioning-phases/SKILL.md`**, **`PHASE_NOTEPAD.md` § E**, and **`BUILD_CHECKPOINTS.md`**.

## Phase model (contracting → operations)

| Phase | ID | Primary users | Route (target) | Writes | BACnet OT |
|-------|-----|---------------|----------------|--------|-----------|
| **0 — Site context** | `site_context` | PM, lead tech | `/commissioning/` or notepad-first | None | None until sign-off |
| **1 — Electrical install** | `electrical` | Electrician, net tech | **`/rough-in/`** (today) | **None** | Who-Is + read PV only (workers) |
| **2 — Point-to-point (Cx)** | `cx_p2p` | HVAC Cx tech | `/commissioning/cx/` or phase tab | **Yes** (gated, audit) | RPM/read/write per `safe-bacnet-writes` |
| **3 — Functional test** | `functional` | Cx, controls lead | `/commissioning/functional/` | As test plan | Sequences, interlocks proof |
| **4 — TAB** | `tab` | TAB contractor | `/commissioning/tab/` | Setpoints / balance | Trends + chart builder |
| **5 — Final BAS** | `operations` | Owner operator | **`/`** supervisor shell | Full RBAC | Live driver, not demo seed |

Phases are **not** linear locks forever — operators may **switch back** (e.g. return to electrical read-only to verify a new device). The UI must show **active phase**, **what is allowed**, and **deep links** to other phase dashboards without losing the shared chat/notepad thread.

## Per-phase dashboard (what to show / hide)

### Phase 1 — Electrical (`/rough-in/`)

**Primary (above the fold):**

1. Phase strip: `Electrical install · Read-only · Writes disabled`
2. Chat (commissioning thread) — short, not worker poll spam
3. **One** BACnet card: bind `IP/prefix:47808`, NIC, last Who-Is, next poll ETA
4. **Device tree** — bind → device → **every** scraped point as a leaf (`object,instance property = value`)

**Collapsed / engineer-only (`<details>`):** networking listeners, flat device table, full point-scrape grid, driver duplicate table.

**Tree UX (required for “good enough” → “field ready”):**

| Requirement | Status (2026-05-18 eval) |
|-------------|----------------------------|
| Nested bind → device → point hierarchy | **Done** — `build_device_tree()` + nested `<ul>` |
| **All** point samples under each device | **Partial** — only objects present in scrape JSON (8 samples / 3 devices in lab); not a full object-list walk |
| **Collapse/expand** per device (default collapsed on mobile) | **Missing** — flat expanded list; margin indent only |
| Click device → scroll/highlight in proof table | **Missing** |
| No duplicate IP/long float in tree meta | **Done** (Playwright guards) |
| Phase selector to other dashboards | **Missing** — single phase pill only |

### Phase 2 — Cx / P2P

**Primary:** same inventory as Phase 1 plus **write/release** controls, priority, reason, audit log panel.

**Hide:** electrician “wire off” copy; show **Cx mode · Writes enabled for staged points only**.

**Backend:** commands must hit **real BACnet** (or lab simulator only when `BAS_BACNET_WRITE_ENABLED=false` in lab). Never expose writes on `/api/public/*`.

### Phase 3 — Functional

**Primary:** test checklists (pass/fail), mode proofs (occupied/unoccupied), alarm verification hooks, optional sequence diagrams.

**Reuse:** point tree with **expected vs actual** columns.

### Phase 4 — TAB

**Primary:** chart builder, CSV export, balance sheets, “all valves open” style macros where modeled.

**Reuse:** trends skill patterns; read-heavy, limited writes.

### Phase 5 — Operations

**Primary:** full `frontend/index.html` shell — nav tree, graphics, alarms, schedules, trends.

**Label clearly:** demo/simulator acceptable on `/` until production driver ships; **never** on `/rough-in/`.

## Shared shell (v2 target)

One **commissioning shell** with:

- `#phase-select` — dropdown or tabs: Electrical | Cx | Functional | TAB | Supervisor
- Persistent **`PHASE_NOTEPAD`** mirror + **§ E phase strip** (done / next / URLs)
- **Same** `rough_in_chat.json` thread across phases
- `localStorage` or server-side `active_phase` — switching phase **does not** clear chat

Implement incrementally: **one vertical slice per Codex mini**; do not rebuild the entire shell in one wake.

## Automation vs Cursor vs human

| Work | Who |
|------|-----|
| Who-Is / point scrape every 5 min | **worker** jobs (`bas-bacnet-discovery-poll`, `bas-bacnet-point-scrape`) |
| UI/tree/phase shell | **Codex** mini or **Cursor** when human-directed |
| BACnet lab sign-off, staging § C | **human** checkbox in `BUILD_CHECKPOINTS.md` |
| Cron / wakes | **paused** during manual experiment — see `workspace-cron` |

When cron is **off**, workers do not run unless started manually; tree data goes stale — UI should show **last poll UTC** and “automation paused” if `jobs.json` jobs are disabled.

## Evaluation snapshot (Cursor, 2026-05-18)

**What Codex did well**

- Live wire integration: discovery JSON + point scrape → public API → tree leaves with rounded PV
- Chat-first layout; advanced proof tables collapsed; worker noise kept out of chat
- Strong regression tests (backend tree, Playwright rough-in smoke)
- Operator labels (`On wire (not in job list)`) vs raw enums

**Gaps (next slices)**

- No collapsible tree; dashboard still **busy** (multiple cards + details)
- Point coverage = scrape samples only, not “every BACnet point” the electrician expects
- No phase switcher or separate phase routes
- **Production runtime:** `bas_app` still uses stdlib `ThreadingHTTPServer` + static `http.server` — fine for lab, not production ASGI (see `web-app-bas` § Production path)

**Verdict:** Phase 1 electrical MVP is **acceptable for lab iteration**, not **impressive** for field sign-off. Queue tree collapse + merge duplicate proof surfaces before Phase 2 writes.
