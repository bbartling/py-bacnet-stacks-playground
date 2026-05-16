---
name: systemd-live-dev
description: >-
  Long-lived BAS dev stack via systemd user units (not Docker): install units,
  restart after code changes, journalctl for errors, health curls between wakes.
  Triggers on: systemd, user unit, bas-backend, bas-frontend, journalctl,
  crash-loop, No module named, POST_WAKE_HOOK, bas_post_wake_stack, 8000, 5173,
  remote dial-in, WorkingDirectory, python3 -m backend, No medium found,
  XDG_RUNTIME_DIR, loginctl enable-linger, codex exec, cron wake shell.
---

# systemd live dev (not Docker)

## Default runtime

- **Do not** use Docker Compose as the primary long-lived runtime unless `BUILD_CHECKPOINTS` explicitly requires it.
- Use **systemd user units** `bas-backend.service` and **`bas-frontend.service`** (create frontend unit if missing — remote UI needs **`:5173`**).
- **Source of truth for commands and ports:** **`bas_app/README.md`** § Run (not old templates that assumed `uvicorn` + `bas_app_backend`).

## Canonical unit files (this repo’s `bas_app` layout)

Install copies under **`~/.config/systemd/user/`**. After edits: `systemctl --user daemon-reload` then `restart` each changed unit.

### `bas-backend.service`

Must match **`cd /home/ben/bas_app && python3 -m backend`** (stdlib package **`backend`** with **`__main__.py`**). **Wrong:** `WorkingDirectory=/home/ben/bas_app/backend` + `python3 -m bas_app_backend` + `PYTHONPATH=src` — that produces **`No module named bas_app_backend`** and empty **`:8000`**.

```ini
[Unit]
Description=BAS head-end API (bas_app stdlib backend)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/ben/bas_app
Environment=BAS_BIND_HOST=0.0.0.0
Environment=BAS_BIND_PORT=8000
# When UI is loaded from the LAN IP, include that Origin (comma list replaces defaults — add loopback too).
Environment=BAS_ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173,http://<head-end-ip>:5173
ExecStart=/usr/bin/python3 -m backend
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
```

### `bas-frontend.service`

Must match **`cd /home/ben/bas_app/frontend && python3 -m http.server 5173 --bind 0.0.0.0`**.

```ini
[Unit]
Description=BAS static frontend (http.server)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/ben/bas_app/frontend
ExecStart=/usr/bin/python3 -m http.server 5173 --bind 0.0.0.0
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
```

## Anti-drift checklist (run after any backend layout change)

| Symptom | Likely cause |
|---------|----------------|
| `No module named bas_app_backend` in journal | Unit still points at old FastAPI / `src` layout |
| `curl http://127.0.0.1:8000/health` fails | Backend not started or wrong `WorkingDirectory` |
| UI static but login never works from LAN | **`:8000`** down; UI alone is not enough |
| Wake log: `post_wake_stack: skip (no …/backend yet)` but `backend/app.py` exists | Default **`bas_post_wake_stack.sh`** gate does not match this tree — **Codex does not depend on patching it:** ship **`bas_app/scripts/`** + README “headless start” and/or point **`POST_WAKE_HOOK`** at that script until ops upgrades the hook |
| `post_wake` starts `uvicorn app.main:app` and dies | Hook command does not match stdlib **`python3 -m backend`** — same: **Path B** in **`BUILD_CHECKPOINTS.md`** |

## `bas_post_wake_stack.sh` (optional hook; not Codex’s only lever)

- May skip or use the wrong start command for this repo’s stdlib layout. **Policy:** Codex delivers **`bas_app/README.md`** + **`bas_app/scripts/`** parity so humans/cron can **`POST_WAKE_HOOK=bash /home/ben/bas_app/scripts/<your>.sh`** without editing `bas_build_spec` binaries.

## Codex / cron wake shells and `systemctl --user`

**Symptom:** `Failed to connect to bus: No medium found` (or `Connection refused` to session bus) when running `systemctl --user`, `journalctl --user`, or `systemctl --user cat …` from **`bas_wake.sh` → `codex exec`**.

**Why:** User **`systemd --user`** talks to **`$XDG_RUNTIME_DIR/systemd/private`** (usually **`/run/user/<UID>`**). Cron and non-interactive Codex shells often have **no** `XDG_RUNTIME_DIR` / `DBUS_SESSION_BUS_ADDRESS`, and there may be **no** active logind session for that UID when the job fires — so there is literally **no user manager bus** in that environment. This is **normal**, not a broken app.

**What Codex should do (in order):**

1. **Detect:** `UID=$(id -u); test -d "/run/user/$UID" && echo "runtime_dir_ok" || echo "runtime_dir_missing"`.
2. **If `runtime_dir_ok`:** prepend commands with **`XDG_RUNTIME_DIR=/run/user/$UID`** (and optionally **`DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus`** if the socket exists):  
   `XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user daemon-reload`  
   `XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user restart bas-backend.service bas-frontend.service`
3. **If `runtime_dir_missing`:** do **not** treat “systemctl failed” as proof the unit file is wrong. Document for operators in **`bas_app/README.md`**:
   - **`sudo loginctl enable-linger <username>`** once (keeps **`user@UID.service`** and **`/run/user/UID`** after boot and without GUI login).
   - Or run **`systemctl --user …` from an SSH login** as that user (interactive session creates the bus).
4. **Always** verify the stack with **Path-agnostic checks** that work from cron: **`ss -ltnp`**, **`curl http://127.0.0.1:8000/health`**. If these pass, the product is up even when `systemctl --user status` cannot run from the wake shell.
5. **Path B (no bus, no linger yet):** implement **`bas_app/scripts/`** start/stop per **`bas_app/README.md`** using **`setsid`/`nohup`** or documented background pattern so **`:8000`** and **`:5173`** listen on **0.0.0.0** — see **`BUILD_CHECKPOINTS.md` Next for mini**.

## Operator scripts

- If **`cron_codex/bin/bas_systemd_manage.sh`** exists in your tree, use it as documented in **`cron_codex/README.md`**. If absent, apply the unit snippets above manually and use **`systemctl --user`**.
- **`POST_WAKE_HOOK`** in `.env` may invoke **`bas_post_wake_stack.sh`** when it matches the tree; **otherwise** point **`POST_WAKE_HOOK`** at a **`bas_app/scripts/`** start script documented in **`bas_app/README.md`** (Codex-owned) so wakes still bring up **:8000** / **:5173**.

## User-bus unavailable fallback

When **`systemctl --user` fails** in the wake shell, use **port + HTTP** checks and **`bas_app/scripts/`** (see above). Do not conclude “backend broken” from bus errors alone.

```bash
ss -ltnp | grep -E ':(8000|5173)\b'
curl -sfS http://127.0.0.1:8000/health
curl -sfSI http://127.0.0.1:5173/
```

Record **bus-unavailable** vs **ports-down** in **`BUILD_CHECKPOINTS.md`**.

## Each mini slice (Codex)

1. Change code in `bas_app/` when the queue says to.
2. Run narrow tests and documented smokes from **`bas_app/README.md`**.
3. **`systemctl --user restart …`** **only when** `XDG_RUNTIME_DIR=/run/user/$(id -u)` works; otherwise document **Path B** and use **`bas_app/scripts/`** for this wake’s proof.
4. **`journalctl --user …`** when the bus exists; otherwise use script logs or `curl`/`ss` only.
5. If **Tier A** in **`BUILD_CHECKPOINTS.md`** is active, paste **runtime proof** into critique (see that file’s **Runtime invariant**).

Bind **0.0.0.0**; document LAN URLs in **`bas_app/README.md`**.

## Related skills

- `web-app-bas`, `workspace-cron`, `spec-validation`
