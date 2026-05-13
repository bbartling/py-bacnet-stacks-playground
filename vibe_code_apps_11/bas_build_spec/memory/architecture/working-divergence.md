# Working architecture divergence log

Append-only. **Status:** `open` | `promoted` | `superseded`.

## 2026-05-11 — Demo auth vs README (open)

- **Expectation:** `bas_app/README.md` documents `POST /api/auth/login` with demo users `admin`/`admin123`, `operator`/`operator123`, `readonly`/`readonly123`; JSON token field `access_token`.
- **Reality (detached stack on :8000):** `POST /api/auth/login` returns **404**; `POST /api/v1/auth/login` returns **401** for README passwords; `operator`/`operator` returns **200** with `role` **Operator** and token key **`token`** (not `access_token`). `admin` and `readonly` README passwords did not authenticate in spot checks.
- **Evidence:** `cron_codex/bin/bas_smoke_login.sh` FAIL on `admin` (404 on `/api/auth/login`); manual curls to `/api/v1/auth/login` on `127.0.0.1:8000`.
- **Cursor action:** `demo_auth.env` and release gate remain README-aligned; divergence logged; queue Codex to align route, credentials, and token field with README or update README after intentional API change.

## 2026-05-13 — Long-lived runtime vs orchestration (open)

- **Expectation:** After wakes, **`bas_app/README.md`** commands keep **`:8000`** (stdlib `python3 -m backend` from `bas_app`) and **`:5173`** (`http.server` from `frontend/`) reachable on **`0.0.0.0`**; **`POST_WAKE_HOOK`** / **`bas_post_wake_stack.sh`** starts the same stack when user systemd is wrong or down.
- **Reality:** **`~/.config/systemd/user/bas-backend.service`** may still use **`python3 -m bas_app_backend`** / wrong **`WorkingDirectory`**, causing **`No module named bas_app_backend`** and no listener on **`:8000`**. **`bas_post_wake_stack.sh`** may **skip** or start **uvicorn** on a path that does not exist for this tree; wake logs can show **`post_wake_stack: skip (no …/backend yet)`** even when **`backend/app.py`** exists. UI on **`:5173`** alone makes login appear “broken.”
- **Evidence:** `journalctl --user -u bas-backend.service`; `ss -ltnp`; `grep post_wake_stack cron_codex/logs/wake-*.log` (tail); **`BUILD_CHECKPOINTS.md`** Tier A + **`skills/systemd-live-dev/SKILL.md`**.
- **Cursor action (historical):** ~~Patch `bas_post_wake_stack.sh`~~ — **superseded:** Codex owns **`bas_app/scripts/`** + **`bas_app/README.md`** (headless start, optional **`POST_WAKE_HOOK`** to that script) and documents **`loginctl enable-linger`** / **`XDG_RUNTIME_DIR=/run/user/$(id -u)`** per **`skills/systemd-live-dev/SKILL.md`**. Tier A proof = **`ss` + `curl`**, not bus access from cron.

## 2026-05-13 — Codex tools: user bus + post_wake (open)

- **Expectation:** Codex closes **Tier A** using **Path A** (`XDG_RUNTIME_DIR=… systemctl --user` when `/run/user/UID` exists) or **Path B** (`bas_app/scripts/` + README; optional **`POST_WAKE_HOOK`** to the script) without editing **`bas_post_wake_stack.sh`**.
- **Reality:** Cron/Codex wake shells often lack a user systemd bus (**`No medium found`**); default **`POST_WAKE_HOOK`** may still **`skip`**.
- **Evidence:** `skills/systemd-live-dev/SKILL.md` § *Codex / cron wake shells*; **`BUILD_CHECKPOINTS.md`** *Next for mini* (Path A / Path B).
- **Codex action:** Implement README + scripts; document **linger** for operators.

## 2026-05-13T15:07Z — Runtime invariant recheck (open)

- **Evidence:** `curl -sfS http://127.0.0.1:8000/health` failed to connect; `ss -ltnp` showed only `0.0.0.0:5173`; `journalctl --user -u bas-backend.service -n 25 --no-pager` still repeated `/usr/bin/python3: No module named bas_app_backend`; `post_wake_stack.log` still showed `post_wake_stack: skip (no /home/ben/bas_app/backend yet)` even though `bas_app/backend/app.py` exists.
