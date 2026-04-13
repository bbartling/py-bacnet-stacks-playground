# Vibe Code App 8 — BAS Lite (**Docker + easy-aso**, no VOLTTRON)

**Operator UI:** TypeScript **React** SPA (**BAS / BMS Lite**) with live points, trends, driver file store, occupancy schedule, and system metrics.

**Backend:** **[easy-aso](https://pypi.org/project/easy-aso/)** supervisor (**FastAPI**, asyncio, SQLite) plus a thin **legacy JSON** layer at **`/app8/api/*`** so the existing SPA keeps working.

**Edge:** **Caddy** on port **80** → static UI (**nginx**) + API. Optional **TLS** + **Basic Auth** patterns live under `docker/caddy/`.

There is **no systemd** requirement for the app layer — only **Docker** (use `restart: unless-stopped`).

---

## Quick start (Raspberry Pi or any Docker host)

1. Install **Docker Engine** + **Compose** (see **[Boss Pi tutorial](docs/BOSS_PI_BAS_LITE_DOCKER.md)**).
2. Ensure **diy-bacnet-server** (or compatible JSON-RPC BACnet) is reachable from containers — default **`http://host.docker.internal:8080`** (see `.env.example`).
3. From this directory:

   ```bash
   docker compose build
   docker compose up -d
   ```

4. Browse to **`http://<host-ip>/`** (redirects to **`/app8/`**).

**Full beginner walkthrough:** [docs/BOSS_PI_BAS_LITE_DOCKER.md](docs/BOSS_PI_BAS_LITE_DOCKER.md)

---

## Repo layout

| Path | Purpose |
|------|---------|
| `docker-compose.yml` | **Caddy** + **api** (easy-aso) + **frontend** (nginx) |
| `docker/bas_lite_api/` | FastAPI image: supervisor + `/app8/api` compatibility |
| `docker/Dockerfile.frontend` | Multi-stage **Node build → nginx** |
| `docker/caddy/Caddyfile` | Reverse proxy routes |
| `frontend/` | React app (`npm run build` runs in Docker) |
| `docs/BOSS_PI_BAS_LITE_DOCKER.md` | **Start here on a new Pi** |
| `volttron_data/` | **Archived** VOLTTRON-era agent copies — see `volttron_data/ARCHIVE_NOTE.md` |

---

## Legacy VOLTTRON bench

If you still need the **VOLTTRON 9 + Platform Driver** bench, use **`vibe_code_apps_6`** in the parent playground repo — not this Docker stack.

---

## Branding

Operator chrome stays **BAS Lite** / **BMS Lite** — not Open-FDD product styling.

---

## License

Follow the parent **py-bacnet-stacks-playground** repo license (typically MIT where noted).
