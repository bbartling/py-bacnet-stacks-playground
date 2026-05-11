# BAS workspace memory (curated bootstrap)

Short standing brief for Codex wakes — not a transcript. Daily detail lives under `memory/YYYY-MM-DD.md`.

## Portfolio / deployment

- Head-end under `bas_app/`; long-lived runtime via **systemd user units** (not Docker).
- Bind **0.0.0.0**; remote operators use server LAN IP.

## Building systems

- *(Per-site equipment, point naming, OAT fan-out / supervisory links — promote from `memory/sites/` and `memory/integrations/bacnet.md` after lab sign-off.)*

## Stack inventory

- Backend: `bas_app/backend/src/bas_app_backend` serves `/health` on `http://127.0.0.1:8000/health`.
- User unit: `bas-backend.service` is installed under `~/.config/systemd/user/` from `bas_build_spec/deploy/systemd/`.
- Frontend: Vite/React app under `bas_app/frontend` serves on `http://127.0.0.1:5173/` and LAN `http://192.168.204.18:5173/` via `bas-frontend.service`.
- Current UI scaffold includes login, navigation tree, equipment point table, OAT supervisory flow strip, and a client-side weekly schedule editor.

## Operator preferences

- Incremental wakes; restart units and read `journalctl --user` after code changes.

## Standing decisions

- Simulator-only default; BACnet gated by `bacnet-driver-lifecycle`.

## Open loops

- *(Follow-ups not yet in cron or checkpoints.)*
