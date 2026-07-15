---
name: vibe20-sketchbox
description: >-
  Bridge Vibe19 Open-FDD findings to Slipstream Sketchbox ECM analysis via the
  vibe_code_apps_20 agent pack and Playwright drivers. Use when working on
  Sketchbox, measure briefs, ECM savings, vibe20, schedule offsets, or
  browser automation against sketchbox.io.
---

# Vibe20 Sketchbox Bridge

## Before any work

1. Read `vibe_code_apps_20/AGENTS.md` and `.agents/routing.md`.
2. Pick **one** primary skill under `.agents/skills/*/SKILL.md`.
3. Never commit `.env`, cookies, or `.artifacts/sketchbox_storage.json`.
4. Sketchbox has **no public API** — automation is UI-only and best-effort.

## Live drivers (repo root: `vibe_code_apps_20/`)

| Script | Use |
|---|---|
| `sketchbox_driver.py` | `probe` / `login` |
| `explore_sketchbox.py` | Read-mostly tab tour |
| `action_sketchbox.py` | Mutating schedule offset etc. |
| `run_measure.py` | Add Empty Measure + RESULTS |
| `testdrive.py` | Multi-building configure → ECM → RESULTS |

```powershell
cd vibe_code_apps_20
python sketchbox_driver.py login
python testdrive.py --buildings examples/buildings
```

Credentials: `SKETCHBOX_EMAIL` / `SKETCHBOX_PASSWORD` in `.env` only.

## Hard constraints (non-negotiable)

- Evidence → applicability → baseline → proposed change → results. Never invent savings.
- One ECM at a time; do not attribute interaction-coupled savings as independent.
- UI failure → `BLOCKED_UI_CHANGE` + artifacts; leave project recoverable.
- Project names: ASCII hyphens only (Sketchbox rejects em dash `—`).
- Cooling thermostat offset max **5°F** in Sketchbox UI.
- Tabs: `div.view-link[view="project|schedules|measures|results"]` (lowercase).

## Schemas

Validate against `schemas/building_profile.schema.json`, `measure_brief.schema.json`, `result_record.schema.json`. Examples under `examples/` and `examples/buildings/`.

## Status vocabulary

`READY` | `NEEDS_INPUT` | `NEEDS_ENGINEERING_REVIEW` | `BLOCKED_UI_CHANGE` | `BLOCKED_AUTH` | `MODEL_RUN_FAILED` | `RESULTS_SUSPECT` | `COMPLETE`

## Integrity sequence (testdrive)

1. Configure PROJECT (ASCII hyphen names only).
2. Zero thermostat offsets → scrape **true baseline** RESULTS.
3. Apply **approved** measures only → scrape measure case.
4. Emit `result_record` with `run_id`, `input_hash`, `quality_flags`.

Use `python testdrive.py --dry-run` before live writes. Shared selectors live in `sketchbox_ui.py`.
