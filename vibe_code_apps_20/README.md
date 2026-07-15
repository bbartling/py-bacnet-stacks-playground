# Vibe App 20 — Sketchbox Agent Engineering Pack + Live Drivers

Bridge from **Vibe App 19 / Open-FDD** findings to conceptual [Sketchbox](https://www.sketchbox.io/) ECM analysis (Slipstream / DOE-2).

## Design principles

1. **Evidence before modeling.** An FDD result is not automatically an ECM.
2. **Measure briefs are authoritative.** Sketchbox has no documented public API; browser automation is a best-effort accelerator.
3. **One change at a time.** Preserve Sketchbox's individual, progressive measure workflow.
4. **Never hide assumptions.** Every inferred input carries provenance, confidence, and review status.
5. **Baseline integrity comes first.**
6. **Human review gates irreversible actions.**
7. **State is captured after every major UI transition** under `.artifacts/` (gitignored).

Start here: [`AGENTS.md`](AGENTS.md) → [`.agents/routing.md`](.agents/routing.md).

Cursor skill entrypoint: [`.cursor/skills/vibe20-sketchbox/SKILL.md`](.cursor/skills/vibe20-sketchbox/SKILL.md) (mirrors into repo-root `.cursor/skills/` for discovery).

## Live drivers (working)

| Script | Role |
| --- | --- |
| `sketchbox_driver.py` | `probe` / `login` — auth + storage state |
| `sketchbox_ui.py` | Shared selectors + read-back writes |
| `explore_sketchbox.py` | Read-mostly tab tour (SCHEDULES / MEASURES / RESULTS) |
| `action_sketchbox.py` | Mutating actions (e.g. cooling setpoint offset) |
| `run_measure.py` | Add Empty Measure + wait RESULTS |
| `testdrive.py` | Multi-building: baseline → approved ECM → measure case |

```powershell
cd vibe_code_apps_20
copy .env.example .env   # set SKETCHBOX_EMAIL / SKETCHBOX_PASSWORD
python sketchbox_driver.py probe
python sketchbox_driver.py login
python testdrive.py --dry-run --buildings examples/buildings
python testdrive.py --buildings examples/buildings
```

Fable 5 critique: [`docs/FABLE5_CRITIQUE.md`](docs/FABLE5_CRITIQUE.md).

FDD → Sketchbox workflow (vibe19 bridge intent): [`docs/FDD_TO_SKETCHBOX_WORKFLOW.md`](docs/FDD_TO_SKETCHBOX_WORKFLOW.md).

### Madison Liberty conceptual screen

```powershell
python run_madison_concept.py --dry-run
python run_madison_concept.py --probe-only
python run_madison_concept.py
```

Profile: `examples/buildings/madison_liberty_concept.json` (anonymized Madison weather only; uncalibrated).
Every export includes the conceptual screening disclaimer.

## Credentials

- Only in `.env` (gitignored). Never commit cookies / `sketchbox_storage.json`.
- Env: `SKETCHBOX_EMAIL`, `SKETCHBOX_PASSWORD`, `SKETCHBOX_BASE_URL`, `SKETCHBOX_HEADED`, `SKETCHBOX_SLOW_MO_MS`.

## Package layout (from agent pack)

| Path | Role |
| --- | --- |
| `.agents/skills/*/SKILL.md` | Domain + operator skills |
| `.agents/workflows/` | End-to-end + recovery |
| `.agents/checklists/` | Readiness / write / QA gates |
| `schemas/` | `building_profile` / `measure_brief` / `result_record` |
| `examples/` | Sample JSON |
| `docs/` | Architecture, Sketchbox knowledge, roadmap |
| `ecm_library/` | ECM notes |

## Primary workflow

`Vibe 19 export → evidence normalization → ECM candidates → engineering review → Sketchbox baseline → progressive measures → results validation → ranked RCx package`

See [`INTEGRATION_PATCH_GUIDE.md`](INTEGRATION_PATCH_GUIDE.md) for remaining hardening (dry-run flags, redaction, Pydantic models).
