---
name: web-app-bas
description: >-
  Use when working on the BAS supervisory web app (React/TS or chosen SPA),
  auth shell, navigation tree, REST/WebSocket APIs, systemd user units, or dev
  server bind 0.0.0.0. Triggers on: frontend, backend, API, login, RBAC,
  bas_build_spec, head-end, POST_WAKE_HOOK, simulator service, BACnet driver
  lifecycle, remote dial-in, localhost confusion, Caddy port 80 conflict, LAN IP bookmark.
---

# Web app — BAS head-end

## Source of truth

1. **`bas_build_spec/spec.md`**
2. **`bas_build_spec/acceptance_criteria.md`**
3. **`bas_build_spec/BUILD_CHECKPOINTS.md`** — Codex wake queue.
4. **`bas_build_spec/cron_codex/README.md`** — automation, hooks, cron self-removal.
5. **`bas_build_spec/skills/systemd-live-dev/SKILL.md`** — long-lived `bas_app` via user systemd (not Docker).

## Live access

- Dev and demo stacks should listen on **`0.0.0.0`** when remote dial-in is required; document host/port and firewall expectations (see **`bas_build_spec/cron_codex/README.md`** and **`bas_app/README.md`** § Dial-in).

### `localhost` vs remote (do not regress)

- **`http://localhost:5173/`** from an engineer’s **laptop** hits the **laptop**, not the head-end server. Remote operators must use **`http://<server-lan-ip>:5173/`** (UI) and **`http://<server-lan-ip>:8000/`** (API) for the default two-port layout, or a **single** documented origin if Caddy/nginx proxies per **`bas_app/deploy/Caddyfile.example`**.
- In **`bas_app/README.md`**, keep the **dial-in table** accurate; in UI copy, avoid implying “open localhost from any PC.”

### Port 80 / Caddy (conflicts)

- Another app on **`:80`** (often **Caddy**) is **not** the BAS static server. Do **not** add Caddy/nginx site blocks unless the sprint explicitly owns reverse-proxy work — it confuses “what URL is the BAS?”
- To **remove** lab web stacks on a server (Caddy + optional post-wake listeners), humans run **`sudo bash bas_build_spec/cron_codex/bin/bas_strip_lab_web.sh`** (see script header). Codex does **not** run that script without explicit human direction.

## Phased BACnet vs simulator (`bas_app`)

1. **Default:** **`bas_app`** stays **simulator/in-memory** (see **`bas_app/backend/README.md`**) — UI and APIs ship without a BACnet runtime.
2. **After lab gate:** Follow **`bacnet-driver-lifecycle`**: technician sign-off on **Who-Is / I-Am / object-list** output, then structured discovery artifacts, then a **BACpypes3** driver patterned on **`bas_build_spec/bacnet_scripts.md`**, then wire the same domain services the UI already uses.
3. Do **not** interleave random wire traffic in hourly automation unless **`BUILD_CHECKPOINTS`** explicitly schedules that lab slice.

## First slice

- Start with the BAS shell: auth/login, left navigation tree, top status bar, and a main pane that can host equipment graphics and point tables.
- **Shell / schedules:** **`schedule_example.html`**. **Wire-sheet / synoptic panes:** **`n4_graphic.html`** (same as `graphic.html`) for flow-strip density and status colors — see **`bas-graphics/references/frontend-examples.md`**.
- Keep simulator-backed APIs behind interfaces so later BACnet or gateway drivers can replace them without reshaping the shell contract.

## Repo-local skills layout

All task skills live under **`bas_build_spec/skills/<name>/SKILL.md`** (this tree). Cursor picks them up via symlinks in **`~/.cursor/skills/`** (see root **`bas_build_spec/skills/README.md`**).

## Related skills

- `bas-graphics`, `alarm-workflows`, `trend-data`, `safe-bacnet-writes`, `bacnet-point-modeling`, `bacnet-driver-lifecycle`, `brick-schema-modeling`
