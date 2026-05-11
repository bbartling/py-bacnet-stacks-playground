---
name: workspace-memory
description: >-
  OpenClaw-style workspace memory for BAS Codex wakes: MEMORY.md bootstrap,
  daily notes, domain files, promotion after critique, no secrets in Markdown.
---

# Workspace memory

## Layout

- **`bas_build_spec/AGENTS.md`** — agent orientation and bootstrap order.
- **`bas_build_spec/MEMORY.md`** — curated bootstrap (short; every wake).
- **`bas_build_spec/scratch/memory-bootstrap-latest.md`** — regenerated each wake (truncated injection).
- **`bas_build_spec/memory/YYYY-MM-DD.md`** — append-only daily wake log.
- **Domain:** `memory/sites/`, `buildings/`, `equipment/`, `integrations/`, `stack/`, `operators/`.

## Rules

- Do not paste full `spec.md` into memory files.
- After each wake, critique appends to today’s daily file (failures, smoke, URLs, risks).
- Promote only stable facts into `MEMORY.md` and domain files.
- **`BUILD_CHECKPOINTS.md`** remains the ordered mini queue; memory holds building + stack context.
- As patterns stabilize, add short notes to **`skills/*/references/`** (not full spec pastes).

## Operator CLI

```bash
bas_build_spec/cron_codex/bin/bas_workspace_cli.sh memory list
bas_build_spec/cron_codex/bin/bas_workspace_cli.sh memory search <term>
bas_build_spec/cron_codex/bin/bas_workspace_cli.sh memory bootstrap
```

## Recall

- v1: truncated bootstrap file + path reads + `memory search`.
- v2 (later): optional embeddings — not required for current wakes.
