---
name: field-commissioning-phases
description: >-
  Use when scoping electrician read-only dial-in dashboards, BACnet driver health,
  guided PHASE_NOTEPAD onboarding (LAN topology, BACnet bind, paste prompts),
  commissioning chat (HVAC type, expected BACnet devices), bare-bones tables,
  dark/light mode, persisted conversation across phases, networking/NIC tab,
  HVAC Cx P2P writes, TAB chart builder, or in-app notepad Save. Triggers on:
  PHASE_NOTEPAD, paste ur info, BACnet bind, commissioning chat, bare bones,
  strip down rough-in, dark mode light mode, 192.168, topology, BBMD, 47808,
  5173, 8000, commissioning, electrician, Cx, TAB, notepad dashboard,
  no login electrician, public rough-in.
---

# Field commissioning — construction-realistic phases

## Intent

Model **field BAS sequencing**: **guided site context (BACnet LAN + topology)** → **electrician read-only surfaces** → **Cx / P2P** → **TAB charts** → **final BAS**. The **notepad** (`PHASE_NOTEPAD.md`) is the **contract** between human and agent; an **in-app notepad** (when built) must **mirror** the same prompts and **always** show a **phase summary strip** (done / next / URLs).

## Canonical sources

1. **`bas_build_spec/spec.md`** — § *Commissioning and construction phases*
2. **`bas_build_spec/memory/commissioning/PHASE_NOTEPAD.md`** — **structured** LAN, BACnet bind, building, devices, URLs, **§ E phase strip**
3. **`bas_build_spec/BUILD_CHECKPOINTS.md`** — queue; mini picks **one** slice
4. **`bas_build_spec/bacnet_scripts.md`** — bind string patterns (`--address IP/prefix[:47808]`)
5. **`references/commissioning-ui-language.md`** — **no simulator branding** on `/rough-in/`; operator labels for BACnet status + devices
6. **`skills/web-app-bas`**, **`bacnet-driver-lifecycle`**, **`safe-bacnet-writes`**, **`workspace-memory`**

## Phase ladder (summary)

| Phase | Who | Dashboard / UX | Writes |
|-------|-----|----------------|--------|
| **0 — Site context** | PM / lead | Notepad + paste prompts; no OT until sign-off | **None** |
| **1 — Electrical install** | Electrician / net tech | **`/rough-in/`** — chat + bind + **collapsible device tree** (all scraped PVs) | **None** |
| **2 — Cx + HVAC P2P** | Commissioning tech | Phase dashboard: P2P + **writable** tests + audit | **Yes** (staged only) |
| **3 — Functional test** | Cx / controls | Checklists, modes, expected vs actual | As test plan |
| **4 — TAB** | TAB contractor | Chart builder + balance evidence + export | As needed |
| **5 — Final BAS** | Owner operator | **`/`** full supervisor shell | Full RBAC |

**Detailed routes, show/hide rules, tree UX scorecard, and eval notes:** **`references/commissioning-phase-dashboards.md`** (read before any multi-phase UI mini).

### Phase switching (required in v2 shell)

- One **commissioning shell** URL for the job life; **`#phase-select`** or tabs: Electrical | Cx | Functional | TAB | Supervisor.
- Switching phase **must not** reset chat (`rough_in_chat.json`) or notepad facts.
- Each phase gets its **own primary dashboard layout** (not one page with every table visible).
- Operators may **go back** to earlier phases (e.g. electrical read-only after a new device is powered).
- **Public** routes stay read-only until phase ≥ 2; writes only on authenticated Cx+ APIs — never `/api/public/*`.

## Notepad app — LLM + human behavior (v1 markdown, v2 in `bas_app`)

### v1 (today): `PHASE_NOTEPAD.md` in git

- **On every commissioning-related wake**, the agent **reads `PHASE_NOTEPAD.md` first** (after `GUARDRAILS.md` / wake prompt).
- **`cron_codex/state/rough_in_chat_since_last_wake.md`** — auto-exported at wake start: **all** rough-in chat messages **since `jobs-state.json` `bas-wake-hourly.last_run_at`**. Validate with **`bas_validate_wake_chat_slice.sh`**. Do not rely on `rough_in_chat_summary.md` alone (latest turn only).
- **If § A–D are still `(fill)` or empty**, the agent must **not assume** BACnet topology. It should:
  1. Append **`next_directions.md`** (or `BUILD_CHECKPOINTS` “Next for mini”) with **concrete questions** for the human, **or**
  2. If implementing UI this slice: surface the **exact Step 1 prompt** from the notepad file (“**Paste your info into me** … BACnet bind, LAN topology, building, devices, dial-in URLs”).
- **BACnet bind** belongs **in the notepad** (and in-app mirror), e.g. `<head-end-ip>/prefix:47808` per **`bacnet_scripts.md`** — not only in chat. **Never** hard-code a job's OT subnet in this skill.

### v2 (in `bas_app`): unified commissioning shell (Day 0 → months on site)

When **`BUILD_CHECKPOINTS`** schedules UI, build toward **one shell** (same dial-in URL for the life of the job) whose **layout mimics construction months**—**phase** gates writes and which **tabs** are primary.

Implement **incrementally** (one vertical slice per mini when possible). Target layout:

1. **Step 1 + chat / notepad** — **Paste your info into me** (same copy as `PHASE_NOTEPAD.md` § Step 1); **Save** → `PHASE_NOTEPAD.md` or exportable sidecar + README path.
2. **Always-open strip** — Active **phase**, **done**, **next**, **UI/API URLs + ports**, **BACnet bind** last saved, **driver health** summary.
3. **Read-only telemetry (beside notepad on Day 0)** — After save, show **point / device** values the backend can read (wire when signed off, else staged/gated); **no writes** until phase ≥ Cx. Label wire state per **`commissioning-ui-language.md`**, not “simulator”.
4. **Build criteria panel** — Checkboxes for **`acceptance_criteria.md` commissioning roadmap** rows; tie to **human ops** commands where practical: buttons or deep links for **`bas_validate_cron_services.sh`**, **`bas_validate_wake_pass.sh`**, **`bas_validate_automation.sh`** (or show **last result** + path to **`cron_codex/logs/wake-*.log`** per `vibe_code_app_11_notes.txt` § 3–4); **never** auto-run `sudo`.
5. **Electrician zone** — **No login:** dedicated **public** route (not the operator sign-in shell); device **online/offline/comm** (red/amber/green); **points + sensor values**; read-only; large **paste** area for site context (see `PHASE_NOTEPAD` § Step 1).
6. **Technician (Cx) zone** — Same inventory with **write/release** + reason + audit when phase allows.
7. **TAB zone** — **K-factor / balance** fields where modeled, **sequencing** or **hydronic** demos (e.g. **all valves open** for balance pass), **setpoint** tweaks, **chart builder** + CSV for sign-off.
8. **UX (human override 2026-05-15)** — **Bare bones**, not dense BAS chrome: minimal color (neutral grays; status only green/red/amber). **Chat-first** at top (HVAC system type, expected BACnet devices on site). Below: **plain HTML tables** for BACnet status, networking, device/point values. **Dark / light** toggle on every commissioning phase surface. **One persisted conversation thread** per job (survives phase changes and page reloads)—human ↔ agent dialog is the primary UX; tables are secondary readouts.

### Device tree (Phase 1 — non-negotiable for “field ready”)

Current implementation (`frontend/rough-in/app.js` `renderDeviceTree`) renders a **fully expanded** nested `<ul>` with indent only — **not** acceptable as the final electrician UX.

**Next slices must include:**

1. **Per-device collapse** — `<details>` or `aria-expanded` toggle; default **collapsed** except bind root; remember state in `sessionStorage` per device id.
2. **All scraped points as leaves** — one row per sample in `bacnet_point_samples_latest.json`; label `object-type,instance property = value` (already partially done via `tree-point-row`).
3. **Single OT surface** — do not require operators to open a second point-scrape table for the same data; proof tables stay in `<details>` for engineers only (see **`commissioning-ui-language.md`**).
4. **Optional:** expand-all / collapse-all control for large sites.

**Do not** claim “every BACnet point on device” until object-list scrape or RPM is implemented — say **“points from last scrape”** in subtitle if coverage is sample-based.

### Cursor / human experiment — cron off

When the human pauses automation for manual iteration:

1. `bas_remove_cron_marked.sh` + set **`enabled: false`** on all jobs in **`cron/jobs.json`**.
2. Document in **`BUILD_CHECKPOINTS.md`** Current sprint — workers will not refresh discovery/scrape until re-enabled or run manually.
3. Rough-in UI should still show **last poll UTC**; add “automation paused” if jobs are disabled (optional mini).

Re-enable: `bas_install_cron.sh`, flip jobs back on, verify `bas_validate_cron_services.sh`.

The **LLM** treats **empty notepad § A–D** as **blocking** for claiming BACnet/electrician work “complete.”

**Polling requests in chat:** phrases like “start polling” or “real data in the table” mean the operator wants wire data — queue **Who-Is** after sign-off, not endless “simulator” UI. Do not treat **gated pending** as a hung driver.

**Operator-facing copy:** follow **`references/commissioning-ui-language.md`** — purge “Simulator-only path”, `simulator_only`, and “simulator mock” from rough-in **BACnet / driver status** and device tables. Internal enums may stay; **display labels** must be field language (wire off / pending Who-Is / discovering / polling).

**Who-Is:** mandatory **first wire step** after human checks **§ BACnet lab sign-off** in `BUILD_CHECKPOINTS.md`, using bind/NIC from **`PHASE_NOTEPAD.md` § A**. Log I-Ams to **`memory/integrations/bacnet.md`**. Cross-check discovered addresses against **§ C** (fix chat typos in notepad, not in generic skills).

## Agent rules

- **Read notepad first**; **ask** before inventing LAN/BACnet context.
- **One vertical slice per mini** when not also expanding another new skill folder (`GUARDRAILS`).
- **Simulator-first** until `bacnet-driver-lifecycle` human sign-off.
- **Dial-in:** `web-app-bas` — bind `0.0.0.0`, **UFW**, **`BAS_ALLOWED_ORIGINS`**.
- After skill edits: **`bas_skills_link.sh`**.

## Related skills

- `web-app-bas`, `bacnet-driver-lifecycle`, `bacnet-point-modeling`, `safe-bacnet-writes`, `alarm-workflows`, `trend-data`, `bas-graphics`, `workspace-memory`, `systemd-live-dev`
