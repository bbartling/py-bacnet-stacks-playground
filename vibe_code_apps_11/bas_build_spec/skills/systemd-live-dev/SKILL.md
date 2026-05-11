---
name: systemd-live-dev
description: >-
  Long-lived BAS dev stack via systemd user units (not Docker): install units,
  restart after code changes, journalctl for errors, health curls between wakes.
---

# systemd live dev (not Docker)

## Default runtime

- **Do not** use Docker Compose as the primary long-lived runtime unless `BUILD_CHECKPOINTS` explicitly requires it.
- Use **systemd user units** `bas-backend.service` and `bas-frontend.service`.
- Templates: `bas_build_spec/deploy/systemd/`; installed copies under `bas_app/deploy/systemd/` and `~/.config/systemd/user/`.

## Operator scripts

- **`cron_codex/bin/bas_systemd_manage.sh ensure-restart-health`** — refresh units, restart, curl `/health` and UI port.
- **`POST_WAKE_HOOK`** should point at this script (or `bas_post_wake_stack.sh` with `BAS_RUNTIME=systemd`).

## Each mini slice

1. Change code in `bas_app/`.
2. Run narrow tests (import, curl, `npm run build` when feasible).
3. **`systemctl --user restart bas-backend.service`** (and frontend when UI changed).
4. **`journalctl --user -u bas-backend.service -n 40 --no-pager`** — fix errors before ending the slice.
5. Record results in `BUILD_CHECKPOINTS.md` and today’s `memory/YYYY-MM-DD.md`.

Bind **0.0.0.0**; document LAN URLs in `bas_app/README.md`.
