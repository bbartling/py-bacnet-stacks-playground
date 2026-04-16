# Vibe Code App 8 — BAS Lite (**easy-aso** multi-agent edge stack, API **v1.5.0**)

This directory is the **active** App 8 operator stack: **React** UI + **`bas_lite_api`** (Python **v1.5.0**, pins **`easy-aso[platform]==0.1.7`** from **PyPI**) + **diy-bacnet-server** (BACnet / JSON-RPC) behind **Docker Caddy** + **nginx** for static **`/app8/`**.

**Multi-agent:** optional Compose profile **`agents`** runs three **RPC-docked** sidecars (`easy-aso-agent` CLI, **`RpcDockedEasyASO`**): **OAT share**, **GL36-style VAV request / trim-respond feed**, and **AHU supply-air reset** — all BACnet I/O over **JSON-RPC** to **diy-bacnet** (no second **UDP 47808** bind). Profile **`oat`** keeps the lightweight legacy **easy-aso-oat** loop. See **`docs/BOSS_PI_BAS_LITE_DOCKER.md`** §9 and **`.env.example`**.

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

**Boss Pi deploy (from your Windows PC):** **`.\sync-bas-lite-to-bosspi.ps1`** (full deploy by default: SD-friendly bootstrap, PC-built UI, remote `docker compose`) or **`.\deploy-app8-to-bosspi.ps1`** with the same defaults. Use **`-SyncOnly`** for files-only.

```powershell
.\sync-bas-lite-to-bosspi.ps1 -Target ben@192.168.204.12
.\deploy-app8-to-bosspi.ps1 -SshTarget ben@192.168.204.12
```

Optional deploy flags:

```powershell
.\deploy-app8-to-bosspi.ps1 -SshTarget ben@192.168.204.12 -SyncOnly
.\deploy-app8-to-bosspi.ps1 -SshTarget ben@192.168.204.12 -SdFriendly:$false
.\deploy-app8-to-bosspi.ps1 -SshTarget ben@192.168.204.12 -PrebuiltFrontend:$false
.\deploy-app8-to-bosspi.ps1 -SshTarget ben@192.168.204.12 -SkipFrontendBuild
```

`deploy-app8-to-bosspi.ps1` copies stack files to `~/bas-lite` and runs Pi bootstrap unless `-SyncOnly` is set. Defaults: **`-SdFriendly:$true`** (bootstrap `--sd-friendly`) and **`-PrebuiltFrontend:$true`** (PC `npm run build`, sync `frontend/dist`, Pi Docker skips Vite).

When prebuilding on Windows for Pi deploy, the script sets **`VITE_BASE_PATH=/app8`** during `npm run build` so remote `/app8/` loads JS assets with correct MIME type (prevents `/assets/*.js` resolving to HTML fallback).

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
| `docker-compose.yml` | **diy-bacnet**, **api**, **frontend**, **caddy**; optional **`oat`** / **`agents`** profiles — see **`docs/BOSS_PI_BAS_LITE_DOCKER.md`** §9 |
| `bosspi.env` | LAN + non-default BACnet UDP host port — append to `.env` on Raspberry Pi (see sync script) |
| `run-bas-lite.ps1` | **PowerShell local-only:** build/up/test, optional follow logs (`-FollowLogs`, `-Service api`) |
| `deploy-app8-to-bosspi.ps1` | **PowerShell deploy:** copy to Pi; bootstrap unless `-SyncOnly` (defaults: SD-friendly + prebuilt UI) |
| `sync-bas-lite-to-bosspi.ps1` | Same as deploy with **Pi-first defaults**; use `-SyncOnly` for files-only |
| `scripts/bootstrap-bas-lite.sh` | **Pi / Linux:** merge **`.env`**, auto **BACNET_RPC_API_KEY**, optional `--env-only`, optional `--sd-friendly` |
| `docker/diy-bacnet/` | Image build: clones `bbartling/diy-bacnet-server` at build time |
| `docker/bas_lite_api/` | FastAPI supervisor / driver config / gateway |
| `docker/Dockerfile.frontend` | Multi-stage: Vite **`VITE_BASE_PATH=/app8`** → nginx, or **`FRONTEND_SKIP_NODE_BUILD=1`** uses synced **`frontend/dist`** (Pi-friendly; see deploy defaults) |
| `docker/caddy/` | `Caddyfile` (TLS + auth) and `Caddyfile.local-dev` (HTTP lab) |
| `frontend/` | React source |
| `../vibe_code_apps_8_easy_aso/` | Original easy-aso copy (see **`MOVED_HERE.md`** there); prefer this root |
| `documentation.pdf` / `documentation.txt` | Offline bundle of **`docs/*.md`** (regenerate below; not served by the compose stack) |

---

## Bundled documentation PDF (`documentation.pdf`)

Markdown under **`docs/`** can be turned into **`documentation.pdf`** (and **`documentation.txt`**) using the **parent repo’s** Docker helper (**Pandoc + WeasyPrint**). Run from **`py-bacnet-stacks-playground`** (repo root), not only inside **`vibe_code_apps_8`**:

**Windows (PowerShell)**

```powershell
cd $env:USERPROFILE\Documents\py-bacnet-stacks-playground
.\scripts\docker-docs-pdf\Run-DocsPdf.ps1
```

**Linux / macOS** (from repo root; builds image `py-bacnet-docs-pdf:local` if missing)

```bash
docker build -t py-bacnet-docs-pdf:local -f scripts/docker-docs-pdf/Dockerfile scripts/docker-docs-pdf
docker run --rm -v "$(pwd):/work" -w /work py-bacnet-docs-pdf:local bash scripts/docker-docs-pdf/run.sh
```

That refreshes **`vibe_code_apps_8/documentation.pdf`** from **`vibe_code_apps_8/docs/**/*.md`** (and App 7’s PDF if that tree exists). Details: **`../scripts/docker-docs-pdf/README.md`**.

---

## License

Follow the parent **py-bacnet-stacks-playground** repo license (typically MIT where noted).
