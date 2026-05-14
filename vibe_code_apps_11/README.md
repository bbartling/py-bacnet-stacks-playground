# vibe_code_apps_11 — BAS build spec (orchestration)

This folder holds **`bas_build_spec/`**: BAS product spec, Codex/cron automation, skills, memory, and validation scripts for the head-end build.

- **Application code** (`bas_app/`) is expected at **`/home/ben/bas_app`** in this workspace (sibling of `py-bacnet-stacks-playground/`). Override with **`BAS_APP`** or **`BAS_APP_DIR`** in `bas_build_spec/cron_codex/.env` (see `env.example`).
- **First-time:** `cp bas_build_spec/cron_codex/env.example bas_build_spec/cron_codex/.env` and set paths; `chmod +x bas_build_spec/cron_codex/bin/*.sh` and `bas_cron_engine.py`.
- **Crontab** must use this repo path (e.g. `…/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/…`). Do **not** rely on **`/home/ben/bas_build_spec`** — there is no separate copy outside git; that name was only a compatibility symlink and is removed once cron and skills point here.

See `vibe_code_app_11_notes.txt` for operator runbook snippets.
