# Commissioning memory — per site (not generic spec)

Every OT job is unique: **VLAN, bind NIC, BACnet device instances, HVAC archetype, dial-in URLs**.

## Where site facts live (Codex reads these)

| File | Purpose |
|------|---------|
| **`PHASE_NOTEPAD.md`** | **Live job** — bind, NIC, devices, URLs, phase strip. Human + Codex update each wake. |
| **`PHASE_NOTEPAD.template.md`** | Blank template for a **new** building; copy to `PHASE_NOTEPAD.md` on job start. |
| **`../integrations/bacnet.md`** | Discovery log, I-Am results, validated bind after lab work. |
| **`cron_codex/state/rough_in_chat_since_last_wake.md`** | Generated each wake from chat + pinned notepad (not hand-edited). |
| **`cron_codex/state/next_directions.md`** | Optional wake-specific queue (may reference notepad; avoid hard-coding another site's IPs). |

## What must stay generic

- **`spec.md`**, **`acceptance_criteria.md`**, **`skills/**`** — patterns only (`<head-end-ip>`, `IP/prefix:47808`, “read PHASE_NOTEPAD”).
- **`bacnet_scripts_example/`** — lab patterns with **placeholder** addresses in README/env.example; real bind comes from env + notepad.
- **`BUILD_CHECKPOINTS.md` § BACnet lab sign-off** — checkboxes reference **PHASE_NOTEPAD § A / § C**, not a fixed subnet.

## New job checklist

1. Copy `PHASE_NOTEPAD.template.md` → `PHASE_NOTEPAD.md` (or clear § A–E).
2. Clear `memory/integrations/bacnet.md` wire table (keep header).
3. Replace `next_directions.md` wake paste with notepad-driven text.
4. Run `cron_codex/bin/bas_validate_site_agnostic.sh` — must pass before treating spec as release-ready.
