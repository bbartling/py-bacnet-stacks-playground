# Boss Pi — BAS Lite (Docker + easy-aso + Caddy)

This tutorial is for **beginners** who want the **React “BAS Lite” operator UI** on a Raspberry Pi (**Pi 5 or older 3B+**) using:

- **Docker Compose** (no systemd units for the app — only Docker’s restart policy).
- **[easy-aso](https://pypi.org/project/easy-aso/)** on PyPI (**`0.1.7`** in this stack): asyncio **supervisor** + **FastAPI** (`/api/v1/*`) and legacy JSON for the SPA (`/app8/api/*`), plus **optional multi-agent** sidecars (**§9**).
- **[diy-bacnet-server](https://github.com/bbartling/diy-bacnet-server)** as a **sibling** Compose service (BACnet **UDP 47808** + JSON-RPC on **8080**), with optional **Bearer** RPC auth via **`BACNET_RPC_API_KEY`** (same secret on **diy-bacnet** and **api**).
- **Caddy** (default in this repo: **HTTP-only** `Caddyfile.local-dev` on **`127.0.0.1:18080`**; on Boss Pi set **`CADDY_HTTP_PORTS=18080:80`** in **`.env`** so the UI is reachable from the LAN — see **`.env.example`** (avoid **`0.0.0.0` in `.env`** if the file has Windows CRLF; it can trigger **`Invalid ip address: 0.0.0.`**). Optional TLS + Basic Auth + gateway header via `docker/caddy/Caddyfile`.
- **nginx** serves the static React build under **`/app8/`**.

The operator model borrows **one** idea from classic **Volttron**-style edge stacks (an optional host `vctl` hook exposed by the API for power users); **everything else here is Docker + [easy-aso](https://github.com/bbartling/easy-aso) + diy-bacnet-server**.

---

## 1. Install Docker Engine on Raspberry Pi OS

These steps work on **64-bit Raspberry Pi OS (Bookworm)** on **Pi 5** and **Pi 3B+** (ARM). Use a **64-bit** OS image where possible.

### 1.1 Update the system

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot   # optional but recommended after a large upgrade
```

### 1.2 Install Docker on Raspberry Pi OS

On newer Raspberry Pi OS releases, the Docker convenience script may point at a repo that is not published yet for your codename. If that happens, use the distro package instead.

Try the convenience script first:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
```

If that fails with a Docker apt repo error, install the distro package path instead:

```bash
sudo apt update
sudo apt install -y docker.io
sudo usermod -aG docker "$USER"
sudo systemctl enable --now docker
```

Log out and back in so the **`docker`** group applies.

### 1.3 Install Compose support

```bash
docker compose version
```

If the Compose plugin is missing, try the distro package set in this order:

```bash
sudo apt install -y docker-compose-plugin
# or, if the plugin package is unavailable on your Pi image:
sudo apt install -y docker-compose
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

**Ports:** BACnet **UDP 47808** is published for field devices. On the **host**, diy-bacnet’s container port **8080** is published as **`${DIY_BACNET_PORTS:-127.0.0.1:28090:8080}`** (see **`.env.example`**) so it does not clash with other stacks; inside Compose, **`api`** still uses **`http://diy-bacnet:8080`**. For JSON-RPC from other LAN hosts (rare; increases exposure), set **`DIY_BACNET_PORTS=28090:8080`**.

If you run diy-bacnet **elsewhere** instead, remove or disable the **`diy-bacnet`** service and set **`SUPERVISOR_BACNET_RPC_URL`** (and the same **`BACNET_RPC_API_KEY`**) accordingly. **`host.docker.internal`** remains available on the **api** container for host-published RPC.

---

## 3. Get the stack on the Pi (Git clone)

On the Raspberry Pi (SSH session), clone the monorepo and work inside **`vibe_code_apps_8`** (this folder must contain **`docker-compose.yml`**):

```bash
git clone https://github.com/bbartling/py-bacnet-stacks-playground.git
cd py-bacnet-stacks-playground/vibe_code_apps_8
```

Use your fork URL if you develop on a fork. Pull updates with **`git pull`** (or **`./scripts/bootstrap-bas-lite.sh --git-update`** before compose).

### 3.1 Windows developers (local Docker only)

Use **`scripts/run-bas-lite.ps1`** on your PC for **Docker Desktop** — it does not deploy to the Pi. For the Pi, SSH in and use **§4** / **`bootstrap-bas-lite.sh`**.

### 3.2 Scripts quick reference

| Script | Where it runs | Purpose |
|--------|---------------|---------|
| **`scripts/run-bas-lite.ps1`** | Windows | **Local Docker Desktop:** `compose build` / `up`, optional **`-ProductionFrontend`**, **`-FollowLogs`**. |
| **`scripts/test-bas-lite-http.ps1`** | Windows | Optional HTTP smoke tests against **`http://127.0.0.1:18080`** or **`-BaseUrl`**. |
| **`scripts/bootstrap-bas-lite.sh`** | Pi / Linux | Merge **`.env`**, optional **`--sd-friendly`**, **`--env-only`**, **`--git-update`**, **`--refresh-diy-bacnet`**, **`--diy-bacnet-tests`**. Default: **`docker compose down` → `build` → `up -d`**. **`./scripts/bootstrap-bas-lite.sh --help`** for the full flag list. |

---

## 4. Build and start BAS Lite

Recommended: use the bootstrap script (handles **`.env`**, secrets, CRLF, then compose):

```bash
cd py-bacnet-stacks-playground/vibe_code_apps_8   # or your clone path; must contain docker-compose.yml
chmod +x scripts/bootstrap-bas-lite.sh scripts/troubleshoot-bas-lite.sh   # once
./scripts/bootstrap-bas-lite.sh --sd-friendly
```

Manual equivalent:

```bash
cd py-bacnet-stacks-playground/vibe_code_apps_8
cp .env.example .env
# Edit .env: set BACNET_RPC_API_KEY for OT. For TLS ingress, also set CADDYFILE, BAS_LITE_GATEWAY_TOKEN, BAS_AUTH_HASH.
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f caddy
```

### 4.0a Bootstrap script (details)

**`scripts/bootstrap-bas-lite.sh`** merges **`.env`** from **`.env.example`** (if missing), appends **`bosspi.env`** when **`CADDY_HTTP_PORTS`** is not already set, replaces placeholder **`BACNET_RPC_API_KEY`** with a random hex secret (diy-bacnet and **api** both read **`BACNET_RPC_API_KEY`** — same pattern as Open-FDD generating **`OFDD_BACNET_SERVER_API_KEY`**), strips Windows **`\\r`**, then runs **`docker compose down`**, **`docker compose build`**, **`docker compose up -d`**. Use **`--env-only`** to patch **`.env`** without Docker; **`--help`** for all flags (**`--sd-friendly`**, **`--git-update`**, etc.).

The **api** image installs **`easy-aso[platform]==0.1.7`** from **PyPI** via **`pip install .`** in `docker/bas_lite_api/Dockerfile` (see `docker/bas_lite_api/pyproject.toml`; **bas-lite-api** package version **1.5.0**). Bump the pin there when you intentionally adopt a newer **easy-aso** release, then rebuild **`api`**.

### 4.0 How you reach the UI (loopback vs LAN)

By default, **Caddy** is published on **`127.0.0.1:${CADDY_HTTP_HOST_PORT:-18080}`** (and HTTPS on **`127.0.0.1:${CADDY_HTTPS_HOST_PORT:-18443}`**) unless you override with **`CADDY_HTTP_PORTS`** / **`CADDY_HTTPS_PORTS`**. That default means the operator UI is **only on the Pi itself** unless you use LAN port specs or a tunnel.

| Goal | What to do |
|------|------------|
| **Browser on the Pi** | Open **`http://127.0.0.1:18080/app8/`** (lab **`Caddyfile.local-dev`**) or **`https://127.0.0.1:18443/`** if you mapped TLS to **18443** and use **`Caddyfile`**. |
| **Laptop on the same LAN (“dial in”)** | In **`.env`**, set **`CADDY_HTTP_PORTS=18080:80`** and **`CADDY_HTTPS_PORTS=18443:443`** (two-part forms bind on **all** interfaces — no **`0.0.0.0`** text, so a Windows CRLF `.env` cannot break the IP parser). Allow the port on the Pi firewall (e.g. **`sudo ufw allow 18080/tcp`**). Then open **`http://<pi-ip>:18080/app8/`**. |
| **Keep loopback, still use your laptop** | SSH local forward: **`ssh -L 18080:127.0.0.1:18080 ben@<pi-ip>`** then browse **`http://127.0.0.1:18080/app8/`** on the laptop. |

**TLS + Basic Auth + gateway token (segmented OT LAN):** in **`.env`** set **`CADDYFILE=docker/caddy/Caddyfile`**, **`BAS_LITE_GATEWAY_TOKEN`**, **`BAS_AUTH_*`**, and publish **80/443** on the LAN, for example:

```bash
CADDY_HTTP_PORTS=80:80
CADDY_HTTPS_PORTS=443:443
```

Then open **`https://<pi-ip>/app8/`** (port **443**). Your browser will warn about **Caddy’s internal CA** — trust it on the OT workstation or install Caddy’s local root (see [Caddy `tls internal`](https://caddyserver.com/docs/caddyfile/directives/tls)). You will be prompted for **Basic Auth** (operator credentials from **`.env`**). HTTP on port **80** redirects to HTTPS.

**If you still see `Invalid ip address: 0.0.0.`:** remove any **`CADDY_HTTP_BIND=0.0.0.0`** line from **`.env`**, run **`sed -i 's/\r$//' .env`** on the Pi (strip Windows carriage returns), then use **`CADDY_HTTP_PORTS`** as above.

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

## 9. Runtime model

Supervisory polling, device/point config, and HTTP APIs are handled by **easy-aso** inside the **`api`** container. The React app keeps the same **`/app8/api/*`** JSON shape for pages like Overview, Live points, occupancy schedule (weekly visual + holidays + supervisor point bindings), and **System** (host metrics, Docker container table with **role** labels, **restart / stop / start**, log tail + SSE stream — including optional **easy-aso** sidecars).

**Edge BACnet:** only **`diy-bacnet`** binds **UDP 47808** on the host. Agents and the API use **`JsonRpcBacnetClient`** to the gateway (**device instance** addressing — see **`.env.example`**).

### Optional outside-air share (`easy-aso-oat`, profile `oat`)

Legacy **optional** service **`easy-aso-oat`** (profile **`oat`**) runs a small Python loop: **read** one object via JSON-RPC, **write** to **`OAT_TARGET_WRITES`**. No second BACnet UDP listener.

```bash
docker compose --profile oat up -d easy-aso-oat
```

See **`.env.example`** for **`OAT_SOURCE_*`**, **`OAT_INTERVAL_SEC`**, **`OAT_TARGET_WRITES`**.

### Multi-agent EasyASO sidecars (profile `agents`)

Three **optional** services share one image built from **`docker/easy_aso_agent/`**: **`pip install easy-aso[platform]==0.1.7`**, **`CMD easy-aso-agent run`**, app agents on **`PYTHONPATH=/app`**. Each process is a **`RpcDockedEasyASO`** subclass (`easy_aso.runtime.rpc_docked` on PyPI); BACnet I/O is JSON-RPC to **diy-bacnet** only (**`bacnet_rpm`** is supported when the gateway exposes it).

| Compose service | Label `bas-lite.easy-aso.role` | Module / class | Role |
|-----------------|--------------------------------|------------------|------|
| **`easy-aso-agent-oat`** | `oat-share` | `agents.oat_share_agent` / **`OatShareAgent`** | Same OAT fan-out idea as **`easy-aso-oat`**, full **`on_step`** lifecycle. |
| **`easy-aso-agent-gl36-vav`** | `gl36-vav-requests` | `agents.gl36_vav_requests_agent` / **`Gl36VavRequestsAgent`** | Config-driven VAV **cooling/heating request** counts + optional trim-respond write (**`EASY_ASO_GL36_VAV_CONFIG`** JSON). |
| **`easy-aso-agent-gl36-ahu`** | `gl36-ahu-sat-reset` | `agents.gl36_ahu_supply_reset_agent` / **`Gl36AhuSupplyResetAgent`** | Generic **SAT setpoint reset** from zone temps (**`EASY_ASO_GL36_AHU_CONFIG`** JSON). |

**Bring them all up:**

```bash
docker compose --profile agents up -d easy-aso-agent-oat easy-aso-agent-gl36-vav easy-aso-agent-gl36-ahu
```

Shared env pattern: **`SUPERVISOR_BACNET_RPC_URL`**, **`SUPERVISOR_BACNET_RPC_ENTRYPOINT`**, **`BACNET_RPC_API_KEY`**, plus per-service **`EASY_ASO_AGENT_*`** and step / JSON config vars (see **`.env.example`**).

**Fourth agent (optional):** merge **`docker-compose.easy-aso-agents.example.yml`** for **`easy-aso-agent-extra`** (defaults to **`easy_aso.runtime.sample_agent`** / **`SampleAgent`**).

Edit Python under **`docker/easy_aso_agent/agents/`** and rebuild the image (or bind-mount that folder in a local override compose file).

---

## 10. BACnet bench workflow on Boss Pi

A practical beginner loop after the stack is up:

1. Confirm containers are healthy:

```bash
docker compose ps
docker compose logs --tail=100 diy-bacnet api caddy frontend
# With profile agents:
# docker compose logs --tail=80 easy-aso-agent-oat easy-aso-agent-gl36-vav easy-aso-agent-gl36-ahu
```

2. Confirm the local JSON-RPC BACnet surface answers on the Pi host:

```bash
curl -sS "http://127.0.0.1:${DIY_BACNET_HOST_PORT:-28090}/"
```

3. Open the operator UI through Caddy:

```text
http://127.0.0.1:18080/app8/
```

From another machine, either set **`CADDY_HTTP_PORTS=18080:80`** and use **`http://<pi-ip>:18080/app8/`**, or use an SSH tunnel (see **§4.0**). With the **TLS** `Caddyfile` and **`CADDY_HTTP_PORTS=80:80`** / **`CADDY_HTTPS_PORTS=443:443`**, use **`https://<pi-ip>/app8/`**.

4. Add or verify devices and points through the easy-aso API, then confirm the legacy SPA endpoints reflect them:

```bash
curl -k -u operator:YOUR_PASSWORD https://<pi-ip>/app8/api/health
curl -k -u operator:YOUR_PASSWORD https://<pi-ip>/app8/api/devices
curl -k -u operator:YOUR_PASSWORD https://<pi-ip>/app8/api/points
```

5. Exercise BACnet discovery and point reads from diy-bacnet, then verify the BAS Lite pages update.

If discovery finds two bench BACnet devices, capture their addresses, learned points, and any writeable objects in your bench notes before you change anything.

## 11. Troubleshooting

| Symptom | Check |
|--------|--------|
| UI loads but **no BACnet values** | `docker compose logs api` — RPC URL / **`BACNET_RPC_API_KEY`** mismatch? From the host: `curl -sS "http://127.0.0.1:${DIY_BACNET_HOST_PORT:-28090}/"` should return **200**. |
| **502** from Caddy | `docker compose ps` — is `api` healthy? `docker compose logs api`. |
| **401** on API through Caddy | **`BAS_LITE_GATEWAY_TOKEN`** must match on **caddy** and **api**; Caddy must use the default **`Caddyfile`** (not **local-dev**) when the token is set. |
| **Caddy will not start — port 443 in use** | Common on **Windows** (IIS, Hyper-V, other VPN or proxy tools). Either stop the other listener or change the compose mapping to e.g. **`8443:443`** under **`caddy.ports`** and browse **`https://<host>:8443`**. |
| **`listen udp4 … 47808: bind: address already in use`** | Only one **BACnet/IP** listener per host on **UDP 47808**. Run **`sudo ss -ulnp`** and find **47808** — often another BACnet stack. Stop that process (or remove its container), then **`docker compose up -d`**. Optional: **`BACNET_UDP_HOST_PORT`** in **`.env`** (see **`.env.example`**) for lab-only; standard field traffic stays on **47808**. |
| **Cannot write setpoint** | Driver must be **`bacnet_jsonrpc`** for that device; confirm diy-bacnet write RPC works. |
| **Out of disk** | `docker system df`, prune images, shrink log files. |
| **Frontend image build OOM on Pi** | Prefer PC-built UI: deploy/sync **defaults** set **`FRONTEND_SKIP_NODE_BUILD=1`** and sync **`frontend/dist`**. Or raise **`FRONTEND_NODE_MAX_OLD_SPACE`** in **`.env`** for in-Docker Vite (see **`.env.example`**). |
| **Agents never start** | They are behind profile **`agents`** — run **`docker compose --profile agents up -d …`** (see §9). |

---

## 12. Stack tradeoffs

You get **asyncio**, **typed FastAPI**, **SQLite-backed** config, **hot reload** of drivers, **Docker-first** packaging, **Caddy** edge routing, and **PyPI-installable** core (`easy-aso`). The trade is a focused, smaller stack with fewer moving parts.

When you outgrow the shim, point the React app at **`/api/v1`** directly and drop legacy `/app8/api` routes.
