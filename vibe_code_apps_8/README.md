# Vibe Code App 8 — BAS Lite (**easy-aso stack**, API **v1.5.0**)

This directory is the **active** App 8 operator stack: **React** UI + **`bas_lite_api`** (Python package **v1.5.0**, which pins **`easy-aso[platform]==0.1.5`** from **PyPI**) + **diy-bacnet-server** (BACnet / JSON-RPC) behind **Docker Caddy** + **nginx** for static `/app8/`.

Design inspiration comes from VOLTTRON platform-driver patterns and Open-FDD frontend/operator workflows, now oriented toward AI-assisted deployment/modeling and human-in-the-loop edits.

---

## Quick start (Windows / any Docker host)

1. Install **Docker Engine** + **Compose** (with build + network access for image builds that clone `diy-bacnet-server`).
2. Copy **`.env.example`** → **`.env`** and set secrets (`BACNET_RPC_API_KEY`, `BAS_LITE_GATEWAY_TOKEN` when using the TLS Caddyfile).
3. From this directory:

   ```powershell
   .\run-bas-lite.ps1
   ```

4. Open the UI (defaults bind **loopback** — see `.env.example`):

   - **`http://127.0.0.1:18080/app8/`** (Caddy → nginx frontend; HTTP lab Caddyfile by default)
   - diy-bacnet JSON-RPC on the host: **`http://127.0.0.1:28090/`** (only if you need it directly)

Full operator notes: **`docs/BOSS_PI_BAS_LITE_DOCKER.md`**.

**Boss Pi (copy from your PC):** run **`.\sync-bas-lite-to-bosspi.ps1`**, then on the Pi **`cd ~/bas-lite && ./scripts/bootstrap-bas-lite.sh`**. That script merges **`.env`** from **`.env.example`** + **`bosspi.env`**, generates **`BACNET_RPC_API_KEY`** when it is still the placeholder (same pattern as Open-FDD’s BACnet RPC key), strips CRLF, and runs **`docker compose up -d`**. Use **`--env-only`** to patch **`.env`** without starting Docker.

---

## Layout

| Path | Purpose |
|------|---------|
| `docker-compose.yml` | **diy-bacnet**, **api** (`bas_lite_api`), **frontend** (nginx), **caddy** |
| `bosspi.env` | LAN + non-default BACnet UDP host port — append to `.env` on Raspberry Pi (see sync script) |
| `sync-bas-lite-to-bosspi.ps1` | **PowerShell:** push key compose/Docker/env files to `ben@192.168.204.12:~/bas-lite/` |
| `scripts/bootstrap-bas-lite.sh` | **Pi / Linux:** merge **`.env`**, auto **BACNET_RPC_API_KEY**, optional **`docker compose up -d`** |
| `docker/diy-bacnet/` | Image build: clones `bbartling/diy-bacnet-server` at build time |
| `docker/bas_lite_api/` | FastAPI supervisor / driver config / gateway |
| `docker/Dockerfile.frontend` | Multi-stage: Vite build `VITE_BASE_PATH=/app8` → nginx |
| `docker/caddy/` | `Caddyfile` (TLS + auth) and `Caddyfile.local-dev` (HTTP lab) |
| `frontend/` | React source |
| `../vibe_code_apps_8_easy_aso/` | Original easy-aso copy (see **`MOVED_HERE.md`** there); prefer this root |

---

## License

Follow the parent **py-bacnet-stacks-playground** repo license (typically MIT where noted).
