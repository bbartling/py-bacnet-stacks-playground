---
name: vibe20-sketchbox
description: >-
  Bridge Vibe19 Open-FDD findings to Slipstream Sketchbox ECM analysis via the
  vibe_code_apps_20 agent pack and Playwright drivers. Use when working on
  Sketchbox, measure briefs, ECM savings, vibe20, schedule offsets, or
  browser automation against sketchbox.io.
---

# Vibe20 Sketchbox Bridge

Project-local skill mirror. Canonical copy lives at:
`vibe_code_apps_20/.cursor/skills/vibe20-sketchbox/SKILL.md`

Also load the full pack:

1. `vibe_code_apps_20/AGENTS.md`
2. `vibe_code_apps_20/.agents/routing.md`
3. One primary skill under `vibe_code_apps_20/.agents/skills/`

## Quick commands

```powershell
cd vibe_code_apps_20
python sketchbox_driver.py login
python testdrive.py --buildings examples/buildings
```

Never commit `.env` or `.artifacts/`. Sketchbox has no public API.
