---
name: vibe20-sketchbox
description: >-
  Bridge Vibe19 Open-FDD findings to Slipstream Sketchbox ECM analysis via the
  vibe_code_apps_20 agent pack and Playwright drivers. Use when working on
  Sketchbox, measure briefs, ECM savings, vibe20, GL36, schedule offsets, or
  browser automation against sketchbox.io.
---

# Vibe20 Sketchbox Bridge

## Before any work

1. Read `vibe_code_apps_20/AGENTS.md` (full handbook) and `.agents/routing.md`.
2. Pick **one** primary skill under `.agents/skills/*/SKILL.md` (GL36 → `gl36-airside`).
3. Never commit `.env`, cookies, or `.artifacts/sketchbox_storage.json`.
4. Sketchbox has **no public API** — automation is UI-only and best-effort.

## Live drivers (`vibe_code_apps_20/`)

| Script | Use |
|---|---|
| `sketchbox_driver.py` | `probe` / `login` |
| `sketchbox_ui.py` | Shared selectors + read-back |
| `explore_sketchbox.py` | Read-mostly tab tour |
| `action_sketchbox.py` | Mutating schedule offset etc. |
| `run_measure.py` | Add measure + RESULTS |
| `testdrive.py` | Multi-building configure → ECM → RESULTS |
| `run_madison_concept.py` | Madison: schedule ECM then GL36 proxy + **Save project** |

```powershell
cd vibe_code_apps_20
python sketchbox_driver.py login
python run_madison_concept.py --dry-run
python run_madison_concept.py
```

## Hard constraints

- Evidence → applicability → baseline → proposed change → results. Never invent savings.
- One ECM at a time; schedule before GL36 when 24/7 runtime exists.
- GL36 in Sketchbox is a **proxy** (`VAV Box Minimum` + `Fan Power`), not full Guideline 36.
- Project names: ASCII hyphens only.
- Cooling offset max **5°F**.
- Tabs: `div.view-link[view=...]` lowercase.
- Save online: `.save-project-icon` (`title="Save this project"`) so models appear under Open saved projects.

## Status vocabulary

`READY` | `NEEDS_INPUT` | `NEEDS_ENGINEERING_REVIEW` | `BLOCKED_UI_CHANGE` | `BLOCKED_AUTH` | `MODEL_RUN_FAILED` | `RESULTS_SUSPECT` | `COMPLETE`
