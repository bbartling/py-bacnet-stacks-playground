# vibe_code_apps_20 — Sketchbox ECM bridge (from Open-FDD / vibe19)

Greenfield app that turns vibe19 FDD + analytics exports into **estimated energy
savings** via Slipstream [Sketchbox](https://www.sketchbox.io/) (DOE-2 concept modeling).

## Status

| Track | Goal | Now |
| --- | --- | --- |
| **A** Measure brief | Map vibe19 `fdd_summary.csv` / analytics → ECM JSON for an agent or human | stub soon |
| **B** Local ECM estimates | Order-of-magnitude kWh from motor hours / fault hours / climate | stub soon |
| **C** Sketchbox driver | Playwright login → create/mod project, schedules, run measures | **`sketchbox_driver.py` probe/login** |

## Credentials

1. Copy `.env.example` → `.env`
2. Set `SKETCHBOX_EMAIL` / `SKETCHBOX_PASSWORD` (free Basic plan is fine for UI exploration)
3. Never commit `.env` (gitignored)

```powershell
cd vibe_code_apps_20
copy .env.example .env
# edit .env
python sketchbox_driver.py probe
python sketchbox_driver.py login
```

Screenshots + DOM dumps land in `.artifacts/`.

## Notes

Sketchbox has **no public API** — automation is UI-level and will break when Slipstream
changes the SPA. Prefer exporting a measure brief (A) that a human or agent applies,
and treat Playwright (C) as a best-effort accelerator.
