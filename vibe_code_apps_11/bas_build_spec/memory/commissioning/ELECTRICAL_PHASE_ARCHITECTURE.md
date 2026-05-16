# Electrical / rough-in phase — how the pieces fit

## What `PROMPT_codex_enable_wire_polling.md` is

A **one-time instruction sheet** for a **manual Codex wake** (“turn wire polling on”). It is **not** what runs every 5 minutes. Think of it as a recipe card in `cron_codex/state/` for the builder AI.

## Autonomous arm (commissioning head-ends)

Set **`BAS_BACNET_AUTO_COMMISSION=true`** in `cron_codex/.env`. Worker **`bas_bacnet_auto_commission.sh`** (job every 5 min + start of `bas_wake.sh`) reads **`PHASE_NOTEPAD.md` § A/C**, authorizes wire, enables discovery poll, runs Who-Is. **No paste prompt required.**

## Three layers (do not mix them up)

| Layer | What | LLM? |
|-------|------|------|
| **0. Auto arm** | `bas_bacnet_auto_commission.sh` when flag on | **No** |
| **1. Wire worker** | `bas_bacnet_discovery_poll.sh` every 5 min → `bacnet_discovery_latest.json` | **No** — hard-coded Who-Is |
| **2. Rough-in dashboard** | `/rough-in/` reads JSON → device tree + driver status | **No** — live UI from poll file |
| **3. Rough-in chat** | Status lines from code (discovery + next wake time) | **No LLM by default** — reads same JSON |
| **4. Codex wakes** | Builds `bas_app`, tunes `jobs.json` intervals, full BAS | **Yes** — every ~2h |

**Electrical phase default:** layers **1–3** run without Codex. Codex is for **building** the product and changing poll intervals / UX — not for each Who-Is.

## Human-facing chat expectations

Rough-in chat is **not** ChatGPT/Codex. It should still feel helpful:

- After each user note: short **status** (wire on/off, last poll, I-Am count, devices online).
- **Next Codex wake** time (from `jobs.json` schedule).
- **Next Who-Is poll** (~5 min when job enabled).

Codex wake **reports** go into chat via `post_rough_in_chat_report.py` when the builder runs a slice.

## Device tree (electrical)

Who-Is results → **device tree** on `/rough-in/` (bind → discovered devices → points later). Flat table remains; tree is the primary OT view during Phase 1.
