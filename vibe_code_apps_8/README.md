# Vibe Code App 8 — BAS Lite (**easy-aso stack**, API **v1.5.0**)

This directory is the **active** App 8 operator stack: **React** UI + **`bas_lite_api`** (Python package **v1.5.0**, which pins **`easy-aso[platform]==0.1.5`** from **PyPI**) + **diy-bacnet-server** (BACnet / JSON-RPC) behind **Docker Caddy** + **nginx** for static `/app8/`.

Design inspiration comes from VOLTTRON platform-driver patterns and Open-FDD frontend/operator workflows, now oriented toward AI-assisted deployment/modeling and human-in-the-loop edits.

---

## Quick start (Windows / any Docker host)

1. Install **Docker Engine** + **Compose** (with build + network access for image builds that clone `diy-bacnet-server`).
2. Copy **`.env.example`** → **`.env`** and set secrets (`BACNET_RPC_API_KEY`, `BAS_LITE_GATEWAY_TOKEN` when using the TLS Caddyfile).
3. From this directory:

   ```powershell
   .\run-bas-lite.ps1 -DownFirst
   ```

   Useful local test/log options:

   ```powershell
   .\run-bas-lite.ps1 -NoBuild -FollowLogs
   .\run-bas-lite.ps1 -NoBuild -FollowLogs -Service api
   ```

4. Open the UI (defaults bind **loopback** — see `.env.example`):

   - **`http://127.0.0.1:18080/app8/`** (Caddy → nginx frontend; HTTP lab Caddyfile by default)
   - diy-bacnet JSON-RPC on the host: **`http://127.0.0.1:28090/`** (only if you need it directly)

Full operator notes: **`docs/BOSS_PI_BAS_LITE_DOCKER.md`**.

**Boss Pi deploy (single script from your Windows PC):**

```powershell
.\deploy-app8-to-bosspi.ps1 -SshTarget ben@192.168.204.12
```

Optional deploy flags:

```powershell
.\deploy-app8-to-bosspi.ps1 -SshTarget ben@192.168.204.12 -SyncOnly
.\deploy-app8-to-bosspi.ps1 -SshTarget ben@192.168.204.12 -SdFriendly
.\deploy-app8-to-bosspi.ps1 -SshTarget ben@192.168.204.12 -SkipFrontendBuild
```

`deploy-app8-to-bosspi.ps1` copies stack files to `~/bas-lite` and runs Pi bootstrap unless `-SyncOnly` is set.

Pi bootstrap script and args:

```bash
cd ~/bas-lite
./scripts/bootstrap-bas-lite.sh
./scripts/bootstrap-bas-lite.sh --env-only
./scripts/bootstrap-bas-lite.sh --sd-friendly
./scripts/bootstrap-bas-lite.sh --env-only --sd-friendly
```

`bootstrap-bas-lite.sh` merges `.env.example` (+ `bosspi.env` when present), strips CRLF, generates `BACNET_RPC_API_KEY` if placeholder, and runs `docker compose down && build && up -d` unless `--env-only` is used.

---

## Layout

| Path | Purpose |
|------|---------|
| `docker-compose.yml` | **diy-bacnet**, **api** (`bas_lite_api`), **frontend** (nginx), **caddy** |
| `bosspi.env` | LAN + non-default BACnet UDP host port — append to `.env` on Raspberry Pi (see sync script) |
| `run-bas-lite.ps1` | **PowerShell local-only:** build/up/test, optional follow logs (`-FollowLogs`, `-Service api`) |
| `deploy-app8-to-bosspi.ps1` | **PowerShell deploy:** optional local build check, copy to Pi, run bootstrap (`-SyncOnly`, `-SdFriendly`) |
| `sync-bas-lite-to-bosspi.ps1` | Backward-compatible wrapper around `deploy-app8-to-bosspi.ps1 -SyncOnly` |
| `scripts/bootstrap-bas-lite.sh` | **Pi / Linux:** merge **`.env`**, auto **BACNET_RPC_API_KEY**, optional `--env-only`, optional `--sd-friendly` |
| `docker/diy-bacnet/` | Image build: clones `bbartling/diy-bacnet-server` at build time |
| `docker/bas_lite_api/` | FastAPI supervisor / driver config / gateway |
| `docker/Dockerfile.frontend` | Multi-stage: Vite build `VITE_BASE_PATH=/app8` → nginx |
| `docker/caddy/` | `Caddyfile` (TLS + auth) and `Caddyfile.local-dev` (HTTP lab) |
| `frontend/` | React source |
| `../vibe_code_apps_8_easy_aso/` | Original easy-aso copy (see **`MOVED_HERE.md`** there); prefer this root |

---

## License

Follow the parent **py-bacnet-stacks-playground** repo license (typically MIT where noted).
