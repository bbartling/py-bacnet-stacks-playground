# Boss Pi — BAS Lite without VOLTTRON (Docker + easy-aso + Caddy)

This tutorial is for **beginners** who want the **React “BAS Lite” operator UI** on a Raspberry Pi (**Pi 5 or older 3B+**) using:

- **Docker Compose** (no systemd units for the app — only Docker’s restart policy).
- **[easy-aso](https://pypi.org/project/easy-aso/)** on PyPI: asyncio **supervisor** + **FastAPI** (`/api/v1/*`) and legacy JSON for the SPA (`/app8/api/*`).
- **[diy-bacnet-server](https://github.com/bbartling/diy-bacnet-server)** as a **sibling** Compose service (BACnet **UDP 47808** + JSON-RPC on **8080**), with optional **Bearer** RPC auth via **`BACNET_RPC_API_KEY`** (same secret on **diy-bacnet** and **api**).
- **Caddy** on **80 → 443 redirect**, **TLS internal** (self-signed), **Basic Auth** for the operator UI, and a **gateway-only header** so the API is not meant to be called without going through Caddy (see **`.env.example`**).
- **nginx** serves the static React build under **`/app8/`**.

The old **VOLTTRON + `app8_web_agent`** tree under `volttron_data/` is **archived reference only** — see `volttron_data/ARCHIVE_NOTE.md`.

---

## 1. Install Docker Engine on Raspberry Pi OS

These steps work on **64-bit Raspberry Pi OS (Bookworm)** on **Pi 5** and **Pi 3B+** (ARM). Use a **64-bit** OS image where possible.

### 1.1 Update the system

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot   # optional but recommended after a large upgrade
```

### 1.2 Install Docker (official convenience script)

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
```

Log out and back in so the **`docker`** group applies.

### 1.3 Install Compose plugin (often bundled)

```bash
docker compose version
```

If missing:

```bash
sudo apt install -y docker-compose-plugin
```

### 1.4 Quick test

```bash
docker run --rm hello-world
```

---

## 2. BACnet JSON-RPC (diy-bacnet-server)

easy-aso’s **BACnet JSON-RPC driver** talks to **[diy-bacnet-server](https://github.com/bbartling/diy-bacnet-server)** (or your own JSON-RPC BACnet gateway).

This stack **builds diy-bacnet** from **`docker/diy-bacnet/Dockerfile`**, which **shallow-clones** [diy-bacnet-server](https://github.com/bbartling/diy-bacnet-server) at build time (GitHub’s **default branch**). To pin a revision for reproducible OT builds, vendor a checkout or adjust that Dockerfile. The **api** service defaults to:

`SUPERVISOR_BACNET_RPC_URL=http://diy-bacnet:8080`

For **OT**, set a long random **`BACNET_RPC_API_KEY`** in **`.env`**. The same value is passed to **diy-bacnet** (RPC Bearer enforcement) and **api** (easy-aso’s `JsonRpcBacnetClient` sends `Authorization: Bearer …`). Leave it empty only for quick lab setups.

**Ports:** BACnet **UDP 47808** is published for field devices. HTTP **8080** is mapped to **127.0.0.1** on the host by default so JSON-RPC is not accidentally exposed on the whole LAN; edit `docker-compose.yml` if you need another machine to reach the RPC port directly.

If you run diy-bacnet **elsewhere** instead, remove or disable the **`diy-bacnet`** service and set **`SUPERVISOR_BACNET_RPC_URL`** (and the same **`BACNET_RPC_API_KEY`**) accordingly. **`host.docker.internal`** remains available on the **api** container for host-published RPC.

---

## 3. Copy this folder to the Pi

From your laptop (example):

```bash
scp -r vibe_code_apps_8 ben@192.168.204.12:~/bas-lite
ssh ben@192.168.204.12
cd ~/bas-lite
```

---

## 4. Build and start BAS Lite

```bash
cd ~/bas-lite   # folder that contains docker-compose.yml
cp .env.example .env
# Edit .env: set BAS_LITE_GATEWAY_TOKEN, BACNET_RPC_API_KEY, and a new BAS_AUTH_HASH for your operator password.
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f caddy
```

The **api** image installs **easy-aso** from **PyPI** via **`pip install .`** in `docker/bas_lite_api/Dockerfile` (declared in `docker/bas_lite_api/pyproject.toml`). **JSON-RPC Bearer** (`BACNET_RPC_API_KEY`) requires **easy-aso ≥ 0.1.5**; rebuild after that version appears on PyPI so the resolver picks it up. If you are still on **0.1.3** from PyPI, leave **`BACNET_RPC_API_KEY`** unset unless diy-bacnet is also running without RPC auth.

Open a browser:

`https://<pi-ip>/` (port **443**). Your browser will warn about **Caddy’s internal CA** — trust it on the OT workstation or install Caddy’s local root (see [Caddy `tls internal`](https://caddyserver.com/docs/caddyfile/directives/tls)). You will be prompted for **Basic Auth** (operator credentials from **`.env`**). HTTP on port **80** redirects to HTTPS.

### 4.1 FastAPI OpenAPI (operator debugging)

Caddy exposes **`/openapi.json`** for the machine-readable spec. The React UI already uses the path **`/docs`** for in-app BACnet notes, so **Swagger UI is not mounted on `/docs` through Caddy**.

To browse **Swagger** (`/docs` on the API container), port-forward from your laptop. If **`BAS_LITE_GATEWAY_TOKEN`** is set on **api**, direct calls to the container must send header **`X-Bas-Lite-Gateway-Token: Bearer <same value>`** (except **`GET /api/v1/health`**). For a simple lab, temporarily unset **`BAS_LITE_GATEWAY_TOKEN`** on **api** while using SSH forward only.

```bash
ssh -L 8090:127.0.0.1:8090 ben@PI_IP
# then open http://127.0.0.1:8090/docs
```

REST CRUD for devices/points: **`/api/v1/*`** (see [easy-aso supervisor docs](https://bbartling.github.io/easy-aso/SUPERVISOR_WORKFLOWS.html)).

---

## 5. SD card wear — logs and Docker writes

Pi SD cards fail faster with **constant logging to the card**.

### 5.1 Compose logging (already set)

`docker-compose.yml` uses the **`local`** log driver with **size caps** for `api`, `frontend`, and `caddy`. That avoids huge JSON log files on disk.

### 5.2 Prune periodically

```bash
docker system prune -f
```

### 5.3 SQLite data volume

Supervisor state lives in Docker volume **`bas_lite_data`** mounted at **`/data`** in the API container (`supervisor.sqlite`, schedule JSON, driver config files). That is **bounded** application state — not high-churn logs.

---

## 6. Security model (OT LAN)

This is **not** internet hardening (no rate limits). It **is** meant for a **segmented OT / BAS LAN**:

| Layer | What it does |
|--------|----------------|
| **Caddy `tls internal`** | HTTPS with a **self-signed** site cert (trust Caddy’s local CA or accept the browser warning). |
| **Basic Auth** | Operator login before the SPA or API paths load through Caddy (`BAS_AUTH_USER` + **`BAS_AUTH_HASH`** bcrypt in **`.env`**). |
| **`BAS_LITE_GATEWAY_TOKEN`** | Caddy injects **`X-Bas-Lite-Gateway-Token: Bearer …`** on **`/app8/api/*`**, **`/api/v1/*`**, and **`/openapi.json`** only. The **api** container checks it when the env var is set. The browser **never** holds this secret. Caddy **drops** any client-supplied value with the same header name before proxying. |
| **`BACNET_RPC_API_KEY`** | diy-bacnet-server’s JSON-RPC **Bearer** auth; easy-aso sends the same header when calling RPC. |

**Do not publish** the **api** container port **8090** to the host in production; only **Caddy** should be reachable on **80/443**. Keep **SQLite** and driver data on the named volume.

**Lab without TLS:** set **`CADDYFILE=docker/caddy/Caddyfile.local-dev`** in **`.env`** and leave **`BAS_LITE_GATEWAY_TOKEN`** empty on **api**. That stack uses HTTP on port **80** only (no Basic Auth in Caddy — use only on an isolated lab network).

---

## 7. Related easy-aso documentation

Supervisor workflows and BACnet drivers: **[SUPERVISOR_WORKFLOWS](https://bbartling.github.io/easy-aso/SUPERVISOR_WORKFLOWS.html)**. OT-oriented notes on RPC secrets and exposure: **[Supervisor OT security](https://bbartling.github.io/easy-aso/SUPERVISOR_OT_SECURITY.html)**.

---

## 8. Developer loop on a PC (optional)

```powershell
cd frontend
$env:VITE_DEV_PROXY_TARGET="http://192.168.204.12"
npm install
npm run dev
```

`vite.config.ts` proxies `/app8/api` to the Pi API.

---

## 9. Where did VOLTTRON go?

Supervisory polling, device/point config, and HTTP APIs are handled by **easy-aso** inside the **`api`** container. The React app keeps the same **`/app8/api/*`** JSON shape for pages like Overview, Live points, and Trends.

If you need the **old bench** (Platform Driver + `vctl`), it remains under **`vibe_code_apps_6`** / archived **`volttron_data/`** trees for reference — not used by this Docker stack.

---

## 10. Troubleshooting

| Symptom | Check |
|--------|--------|
| UI loads but **no BACnet values** | `docker compose logs api` — RPC URL / **`BACNET_RPC_API_KEY`** mismatch? From the host: `curl -sS http://127.0.0.1:8080/` should return **200** (diy-bacnet maps **8080** to localhost). |
| **502** from Caddy | `docker compose ps` — is `api` healthy? `docker compose logs api`. |
| **401** on API through Caddy | **`BAS_LITE_GATEWAY_TOKEN`** must match on **caddy** and **api**; Caddy must use the default **`Caddyfile`** (not **local-dev**) when the token is set. |
| **Caddy will not start — port 443 in use** | Common on **Windows** (IIS, Hyper-V, other VPN or proxy tools). Either stop the other listener or change the compose mapping to e.g. **`8443:443`** under **`caddy.ports`** and browse **`https://<host>:8443`**. |
| **Cannot write setpoint** | Driver must be **`bacnet_jsonrpc`** for that device; confirm diy-bacnet write RPC works. |
| **Out of disk** | `docker system df`, prune images, shrink log files. |

---

## 11. “As bad-ass as VOLTTRON?”

You get **asyncio**, **typed FastAPI**, **SQLite-backed** config, **hot reload** of drivers, **Docker-first** packaging, **Caddy** edge routing, and **PyPI-installable** core (`easy-aso`). What you **do not** get out of the box is VOLTTRON’s full **VIP bus**, **historian ecosystem**, and **years of BACnet proxy edge cases** — trade intentionally for a **smaller** modern stack you can own.

When you outgrow the shim, point the React app at **`/api/v1`** directly and drop legacy `/app8/api` routes.
