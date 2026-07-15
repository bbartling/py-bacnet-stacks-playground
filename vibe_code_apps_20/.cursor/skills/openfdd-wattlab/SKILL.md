# OpenFDD WattLab — Cursor skill

Use when working in `vibe_code_apps_20` or when the user asks about OpenFDD WattLab, EnergyPlus ECM screening, easy-button sims, or bridging Open-FDD findings to EnergyPlus.

## Read first

1. `vibe_code_apps_20/AGENTS.md`
2. `vibe_code_apps_20/.agents/routing.md`

## Product

**OpenFDD WattLab** — AI helper from Open-FDD / Vibe 19 evidence → Dockerized EnergyPlus (`energyplus-mcp-dev`) → progressive IDF ECMs → `result_record`.

## Do

- Run `python easy_button.py` / `python madison_office.py` for screens
- Use EnergyPlus-MCP tools for load/validate/inspect/run/plot
- Apply WattLab `idf_patches` for schedule / GL36 proxies
- Scrub any legacy third-party product names from new text

## Don't

- Claim MCP implements full ASHRAE Guideline 36
- Invent savings without evidence
- Skip Docker when claiming a live sim succeeded
