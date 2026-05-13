# Architecture memory

**`working-divergence.md`** — append-only log when **working** `bas_app/` or automation differs from `spec.md`, `acceptance_criteria.md`, or `skills/*/SKILL.md` because the documented path failed or was incomplete.

Cursor agents **record** divergence here and in **`BUILD_CHECKPOINTS.md`**; **Codex CLI** closes gaps in `bas_app/`. Do not patch application code from Cursor to satisfy a checklist item.
