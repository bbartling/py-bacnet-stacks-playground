# Repo-local BAS agent skills (Codex / Cursor architecture)

This directory follows the **OpenAI Codex skill pattern** and the same *shape* as [Phaser’s `skills/` tree](https://github.com/phaserjs/phaser/tree/master/skills): **one task domain per folder**, a required **`SKILL.md`**, and optional **`references/`**, **`scripts/`**, **`assets/`** as the project grows.

**Hard guardrails:** **`GUARDRAILS.md`** (read first) — includes **no surprise Caddy/:80**, **no `localhost` as remote URL**, and **LAN IP / hosts / reverse-proxy** rules for BAS dial-in (`web-app-bas` skill expands this).

## Canonical layout (this repo)

```
bas_build_spec/skills/
  README.md                 # this file
  GUARDRAILS.md
  <skill-folder>/
    SKILL.md                # required — YAML frontmatter + body
    references/             # optional — long tables, vocabulary dumps
    scripts/                # optional — small validators, codegen
    assets/                 # optional — diagrams, JSON samples
```

## Current skills (folders)

| Folder | Role |
|--------|------|
| `bacnet-point-modeling/` | BACnet objects, instances, mapping to supervisory points |
| `brick-schema-modeling/` | Brick / semantic tags, `hasPoint`, equipment relationships |
| `bas-graphics/` | Operator graphics, building-program–aware templates, `graphic.html` theme |
| `alarm-workflows/` | Ack, shelve, lifecycle, routing, BACnet-aligned alarm behavior |
| `trend-data/` | Historian / TSDB abstraction, charts, export |
| `web-app-bas/` | SPA + API + auth shell + links to spec / wakes |
| `safe-bacnet-writes/` | Command workflow, audit, priorities, driver disabled by default |
| `bacnet-driver-lifecycle/` | Human discovery sign-off → inventory → BACpypes3 driver from `bacnet_scripts.md` → wire `bas_app` |
| `bacnet-schedule-motor-verify/` | React weekly schedule (`schedule_example.html`) → BACnet motor writes → read-verify-retry → mismatch + temp alarms; polling/data plane |

## Cursor IDE discovery

Cursor loads project skills from **`~/.cursor/skills/<folder>/`** (workspace `~` here). **Canonical content lives in `bas_build_spec/skills/`**; symlinks under `~/.cursor/skills/` point at these folders so a single source of truth is edited.

Refresh symlinks after cloning (from repo root):

```bash
/home/ben/bas_build_spec/cron_codex/bin/bas_skills_link.sh   # if present; else see cron_codex/README.md
```

*(Script added below.)*

## Codex CLI

Point Codex’s working directory at the repo (`CODEX_CWD`) so relative reads like `bas_build_spec/skills/...` resolve. Wake prompts already inject **`README.md`** and **`GUARDRAILS.md`**.

## When to add a new folder

See **`GUARDRAILS.md`**. Prefer extending an existing `SKILL.md` before adding another top-level domain; **`bacnet-driver-lifecycle`** exists for gated lab → driver → UI work.

## Related

- `bas_build_spec/spec.md`, `acceptance_criteria.md`, `BUILD_CHECKPOINTS.md`, `cron_codex/README.md`
