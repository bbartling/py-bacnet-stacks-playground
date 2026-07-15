---
name: vibe20-sketchbox
description: >-
  Bridge Vibe19 Open-FDD findings to Slipstream Sketchbox ECM analysis via the
  vibe_code_apps_20 agent pack and Playwright drivers. Use when working on
  Sketchbox, measure briefs, ECM savings, vibe20, GL36, schedule offsets, or
  browser automation against sketchbox.io.
---

# Vibe20 Sketchbox Bridge

Canonical handbook: `vibe_code_apps_20/AGENTS.md`

Also: `vibe_code_apps_20/.agents/routing.md` and one primary skill under
`vibe_code_apps_20/.agents/skills/` (`gl36-airside` for Guideline 36 screens).

```powershell
cd vibe_code_apps_20
python run_madison_concept.py --dry-run
python run_madison_concept.py
```

Saves online via Sketchbox `.save-project-icon`. Never commit `.env` or `.artifacts/`.
