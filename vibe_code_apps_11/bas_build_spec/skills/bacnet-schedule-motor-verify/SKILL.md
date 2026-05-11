---
name: bacnet-schedule-motor-verify
description: >-
  Use when wiring the React weekly schedule UI to BACnet (or simulator) drivers,
  motor/fan/pump commands, read-after-write verification, retries, command/status
  mismatch alarms, temperature alarm limits on AI/AV, or polling vs realtime data
  paths. Triggers: schedule_example.html, weekly JSON, WriteProperty, feedback
  read, retry, mismatch, Codex wake, driver polling.
---

# BACnet schedules, motors, and write verification

## Purpose

Deliver a **generic, testable** path from **operator schedule edits** to **field commands** with **verification**, **retries**, and **alarms** — suitable for Codex to implement without hardcoded job-specific BACnet IDs.

## BACnet schedule objects (lab / driver)

- **`bas_build_spec/bacnet_scripts.md`** — **Schedule + Calendar** mini **server** device (`ScheduleObject`, `CalendarObject`, `weeklySchedule`, `exceptionSchedule`, mirrored binary output). Use for lab verification before head-end schedule writes.
- **`bacnet-driver-lifecycle/references/bacnet_scripts_index.md`** — schedule server row + lab ordering.

## UI reference (schedules + shared chrome)

- **`bas_build_spec/frontend_example/schedule_example.html`**
  - React (UMD + Babel) demo: **seven day rows**, **24-hour grid**, **15-minute snap**, **drag + resize blocks**, toolbar, **JSON weekly model** in the preview panel.
  - Production: **React + TypeScript** build; **same interactions and layout** (no CDN Babel/React in prod bundles).
  - Reuse **`:root` design tokens** (`--bg`, `--panel`, `--line`, `--text`, `--muted`, `--accent`, `--block`, `--danger`, `--green`) as the **authoritative shell** for schedules, navigation chrome, forms, dense tables, and dialogs unless a later spec adds a second theme.

## Motor / fan / pump binding (guess until commissioning)

Infer **command** and **feedback** supervisory points from **metadata and naming**; store explicit bindings in seed/config so humans can correct later without code changes.

| Typical role | Often maps to | Feedback / proof |
|--------------|---------------|------------------|
| Fan start/stop | `binary-output`, `binary-value`, or `multistate-value` | `binary-input` / `binary-value` **status**, **Running**, **Proof** |
| Fan speed / VFD | `analog-output` / `analog-value` | **Actual speed** or **Percent** AI/AV |
| Pump | `binary-output` / `binary-value` | **Running** / **Flow** BI or AV |

Each **schedule-to-output binding** should carry: `command_point_id`, `feedback_point_id` (optional), `verify_within_s`, `max_retries`, `retry_backoff_s`, `analog_deadband` (if applicable).

## Write → verify → retry

1. **Scheduler** evaluates weekly + exception JSON → desired command state per bound output (occupancy, enable, start/stop windows).
2. **Driver** issues writes per **`safe-bacnet-writes`** (RBAC, audit, priority, real BACnet **off** unless configured).
3. **Verifier** (worker or driver submodule):
   - After write, **poll read** `Present_Value` on feedback points within `verify_within_s`.
   - Compare command vs feedback with tolerances; **debounce** flapping binaries.
   - **Persistent mismatch** → **Command/Status mismatch** alarm (see **`alarm-workflows`**); show **badge / row state** on schedule UI and alarm list.
4. **Retry** on timeout / error / negative ack: exponential backoff, cap at `max_retries`, then alarm + audit; success clears pending mismatch state.

## Polling vs realtime

- **Realtime channel** (SSE/WebSocket): push high-interest present values and alarm transitions.
- **Interval poll**: full or subset reads for verification, staleness, and historian samples — intervals **configurable** per point class.
- **Telemetry**: follow **`spec.md`** *Telemetry ingestion* — samples tagged with quality/timestamp for trends and forensics.

## Temperature alarms on BACnet sensors

- **Analog Input / Analog Value** points used for space, duct, mixed air, coil, or OA temperatures **must** support **high/low alarm limits**, hysteresis, and **stale/offline** evaluation server-side.
- Surface on **point rows**, **equipment strip** near schedules, and **alarm page** per existing alarm lifecycle rules.

## Codex self-check (robust acceptance)

Before claiming the slice complete:

- Schedule JSON **round-trips** UI ↔ API ↔ persistence.
- **Simulator** can inject **write failure** → visible retries + audit + eventual alarm.
- **Simulator** can hold feedback **wrong** → mismatch alarm + UI indicator within bounded time.
- **Simulator** can push AI **over limit** → analog high/low alarm.
- Unauthorized roles **cannot** persist schedule edits.

## Related skills and docs

- **`bas_build_spec/spec.md`** — DESIGN STYLE (schedule widget + theme), Schedules, Alarms, optional BACnet driver.
- **`bas_build_spec/acceptance_criteria.md`**
- **`safe-bacnet-writes`**, **`bacnet-driver-lifecycle`**, **`alarm-workflows`**, **`web-app-bas`**, **`bas-graphics`** (synoptic / wire-sheet may stay darker inside embedded panes if spec allows).
