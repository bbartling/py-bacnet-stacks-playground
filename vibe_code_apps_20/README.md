# Vibe App 20 — Sketchbox Agent Engineering Pack + Live Drivers

Bridge from **Vibe App 19 / Open-FDD** findings to conceptual Sketchbox ECM screening.

## Design principles

1. **Evidence before modeling.** An FDD result is not automatically an ECM.
2. **Measure briefs are authoritative.** Sketchbox has no documented public API; browser automation is a best-effort accelerator.
3. **One change at a time.** Preserve Sketchbox's individual, progressive measure workflow.
4. **Never hide assumptions.** Every inferred input carries provenance, confidence, and review status.
5. **Baseline integrity comes first.**
6. **Human review gates irreversible actions.**
7. **State is captured after every major UI transition** under `.artifacts/` (gitignored).

**Start here:** [`AGENTS.md`](AGENTS.md) (full agent OS) → [`.agents/routing.md`](.agents/routing.md).

Cursor skill: [`.cursor/skills/vibe20-sketchbox/SKILL.md`](.cursor/skills/vibe20-sketchbox/SKILL.md).

## Live drivers

| Script | Role |
| --- | --- |
| `sketchbox_driver.py` | `probe` / `login` |
| `sketchbox_ui.py` | Shared selectors + read-back |
| `explore_sketchbox.py` | Read-mostly tab tour |
| `action_sketchbox.py` | Targeted mutations |
| `run_measure.py` | Add measure + RESULTS |
| `testdrive.py` | Multi-building approved-ECM screen |
| `run_madison_concept.py` | Madison: schedule ECM then GL36 proxy |

```powershell
cd vibe_code_apps_20
copy .env.example .env   # set SKETCHBOX_EMAIL / SKETCHBOX_PASSWORD
python sketchbox_driver.py login
python run_madison_concept.py --dry-run
python run_madison_concept.py
python testdrive.py --buildings examples/buildings --dry-run
```

## Credentials

Only in `.env` (gitignored). Never commit cookies / `sketchbox_storage.json`.

## Package layout

| Path | Role |
| --- | --- |
| `AGENTS.md` | **Agent handbook (source of truth)** |
| `.agents/skills/*/SKILL.md` | Domain + operator skills |
| `.agents/workflows/` | End-to-end + recovery |
| `.agents/checklists/` | Gates |
| `schemas/` | JSON schemas |
| `examples/` | Profiles + evidence |
| `docs/` | Stub → AGENTS.md |
| `ecm_library/` | ECM notes |

## Primary workflow

`Vibe 19 export → evidence → ECM candidates → review → Sketchbox baseline → progressive measures → validation → RCx package`

See also [`INTEGRATION_PATCH_GUIDE.md`](INTEGRATION_PATCH_GUIDE.md) for remaining hardening.
