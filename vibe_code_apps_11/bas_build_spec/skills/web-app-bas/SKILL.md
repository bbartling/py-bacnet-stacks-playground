---
name: web-app-bas
description: >-
  Use when working on the BAS supervisory web app (React/TS or chosen SPA),
  auth shell, navigation tree, REST/WebSocket APIs, Docker Compose, or dev
  server bind 0.0.0.0. Triggers on: frontend, backend, API, login, RBAC,
  bas_build_spec, head-end, POST_WAKE_HOOK, post_wake_stack, simulator service,
  remote dial-in, LAN CORS preflight, OPTIONS /api/auth/login, Tier A runtime,
  journalctl crash-loop, 8000 down, systemd unit, localhost confusion, Caddy
  port 80 conflict, LAN IP bookmark, favicon 404.
---

# Web app — BAS head-end

## Source of truth

1. **`bas_build_spec/spec.md`**
2. **`bas_build_spec/acceptance_criteria.md`**
3. **`bas_build_spec/BUILD_CHECKPOINTS.md`** — Codex wake queue.
4. **`bas_build_spec/cron_codex/README.md`** — automation, hooks, cron self-removal.

## Definition of done (API + UI + remote)

A feature slice is **not complete** for supervisory work if **only** tests pass on an ephemeral port but **no** long-lived listener matches **`bas_app/README.md`**:

1. **`ss -ltnp`** shows **`0.0.0.0:8000`** (API) and **`0.0.0.0:5173`** (static UI) when the stack should be up.
2. **`curl -sfS http://127.0.0.1:8000/health`** returns **200**.
3. When **`systemctl --user` / `journalctl --user`** are available: **`journalctl --user -u bas-backend.service`** must not show a **restart storm** (`No module named bas_app_backend` — see **`systemd-live-dev`** unit). If the wake shell has **no user bus**, skip journal and prove health with **§1–2** plus **`bas_app/scripts/`** logs documented in README.
4. **`POST_WAKE_HOOK`** may still log **`post_wake_stack: skip`** for this tree — that is OK if **`bas_app/README.md`** documents **`bas_app/scripts/`** (or **`POST_WAKE_HOOK`**) to start **:8000** / **:5173** per README without patching `bas_build_spec`; see **`systemd-live-dev`**.

5. **Remote browser + CORS (mandatory when dial-in is in scope):** Opening **`http://<lan-ip>:5173/`** is not enough. After UFW opens **5173/8000**, the browser sends **`Origin: http://<lan-ip>:5173`**; **`BAS_ALLOWED_ORIGINS`** on **`bas-backend`** must include that exact origin (comma-separated list replaces defaults — include **loopback + LAN** origins). Without it, DevTools shows preflight **`OPTIONS …/api/auth/login`** with **no `Access-Control-Allow-Origin`** and **`net::ERR_FAILED`**. **Proof commands (run on server, substitute LAN IP and host):**
   - `curl -sSI -X OPTIONS "http://<lan-ip>:8000/api/auth/login" -H "Origin: http://<lan-ip>:5173" -H "Access-Control-Request-Method: POST"` → expect **`Access-Control-Allow-Origin: http://<lan-ip>:5173`** (or **`*`** if intentionally using wildcard in isolated lab only).
   - `curl -sS -X POST "http://<lan-ip>:8000/api/auth/login" -H "Origin: http://<lan-ip>:5173" -H "Content-Type: application/json" -d '{"username":"operator","password":"operator123"}'` → **200** + JSON token.
   Codex should add **`Environment=BAS_ALLOWED_ORIGINS=…`** to **`~/.config/systemd/user/bas-backend.service`** (or documented **`EnvironmentFile=`**), **`systemctl --user daemon-reload`**, **`systemctl --user restart bas-backend.service`**, and mirror the same list in **`bas_app/README.md`** dial-in.
6. **Benign 404:** **`python3 -m http.server`** on **5173** often returns **404** for **`/favicon.ico`** — not an API failure. Do not chase as “API 404” unless the path is under **`/api/`**.

## Live access

- Dev and demo stacks should listen on **`0.0.0.0`** when remote dial-in is required; document host/port and firewall expectations (see **`bas_build_spec/cron_codex/README.md`** and **`bas_app/README.md`** § Dial-in).

### `localhost` vs remote (do not regress)

- **`http://localhost:5173/`** from an engineer’s **laptop** hits the **laptop**, not the head-end server. Remote operators must use **`http://<server-lan-ip>:5173/`** (UI) and **`http://<server-lan-ip>:8000/`** (API) for the default two-port layout, or a **single** documented origin if Caddy/nginx proxies per **`bas_app/deploy/Caddyfile.example`**.
- In **`bas_app/README.md`**, keep the **dial-in table** accurate; in UI copy, avoid implying “open localhost from any PC.”

### LAN dial-in triage (short)

1. **`http://<lan-ip>/`** = port **80** — not the default dev UI (**`:5173`**).
2. **Firewall:** allow **5173** and **8000** from the client subnet if the page never loads.
3. **CORS:** UI at **`http://<lan-ip>:5173`** needs **`BAS_ALLOWED_ORIGINS`** to include that origin (or documented **`*`** in isolated lab); restart **`bas-backend`**.
4. **Verify:** `curl -sS -X POST http://<lan-ip>:8000/api/auth/login …` from the remote PC.

**Codex autonomy:** Fix **`bas_app/`** (README, env, systemd) per above; do **not** add new **`[ ]`** rows to **`acceptance_criteria.md`** for routine LAN tuning unless the human reopens scope. Use **`memory/architecture/working-divergence.md`** for transient notes if README lags.

### Port 80 / Caddy (conflicts)

- Another app on **`:80`** (often **Caddy**) is **not** the BAS static server. Do **not** add Caddy/nginx site blocks unless the sprint explicitly owns reverse-proxy work — it confuses “what URL is the BAS?”
- To **remove** lab web stacks on a server (Caddy + optional post-wake listeners), humans run **`sudo bash bas_build_spec/cron_codex/bin/bas_strip_lab_web.sh`** (see script header). Codex does **not** run that script without explicit human direction.

## Validation (spec only — do not edit `bas_app/` from Cursor)

- Follow **`spec-validation`** and `acceptance_criteria.md` release gate.
- Demo credentials and login route are **documented in `bas_app/README.md`** after Codex ships auth.
- **Acceptance:** release gate **Demo auth smoke (curl)** — check `[x]` only after `bas_smoke_login.sh` passes.
- **Operator check:** copy `cron_codex/demo_auth.env.example` → `demo_auth.env`, sync from README, run `cron_codex/bin/bas_smoke_login.sh` (`BAS_BACKEND_HEALTH_URL`).
- On README vs live mismatch, append `memory/architecture/working-divergence.md`; queue Codex in `BUILD_CHECKPOINTS.md`.
- **Auth research:** spec/demo_auth uses `admin`/`admin123`, etc. on `/api/auth/login`. A live stack may differ (e.g. `/api/v1/auth/login`, legacy `operator`/`operator`, token key `token` vs `access_token`) — log divergence; do not patch `bas_app/` from Cursor.

## First slice

- Start with the BAS shell: auth/login, left navigation tree, top status bar, and a main pane that can host equipment graphics and point tables.
- **Rough-in / electrician (Phase 1):** per **`spec.md`** unified shell, add a **separate unauthenticated** page + **public read-only** APIs (path prefix agreed in `BUILD_CHECKPOINTS`) for **paste-your-site**, BACnet health, NIC/listeners, comm/values—**do not** reuse `/api/auth/login` for that surface; keep writes and **`/api/me`** behind Bearer auth.
- Keep the first UI pass aligned with **`bas_build_spec/frontend_example/graphic.html`** so the shell inherits the dark slate surfaces, border chrome, and BAS status colors.
- Keep simulator-backed APIs behind interfaces so later BACnet or gateway drivers can replace them without reshaping the shell contract.
- **Public `/rough-in/`:** never headline “simulator” on BACnet/driver or device tables — map to field labels per **`field-commissioning-phases/references/commissioning-ui-language.md`** (wire off, pending Who-Is, discovering, polling).

## Repo-local skills layout

All task skills live under **`bas_build_spec/skills/<name>/SKILL.md`** (this tree). Cursor picks them up via symlinks in **`~/.cursor/skills/`** (see root **`bas_build_spec/skills/README.md`**).

## Related skills

- `field-commissioning-phases`, `spec-validation`, `bas-graphics`, `alarm-workflows`, `trend-data`, `safe-bacnet-writes`, `bacnet-point-modeling`, `brick-schema-modeling`
