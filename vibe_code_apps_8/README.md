# Vibe Code App 8 — BAS Lite (**Docker + modular VOLTTRON**)

**Operator UI:** TypeScript **React** SPA (**BAS / BMS Lite**) with live points, trends, driver config tools, occupancy schedule, and system metrics.

**Backend:** **VOLTTRON web agent** (`app8_web_agent`) serves static assets and `/app8/api/*`, with live data from `platform.driver` topic publishes and RPC writes.

**Edge:** **Caddy** on port **80/443** for TLS + Basic Auth in front of the VOLTTRON web endpoint.

This stack runs in Docker but keeps VOLTTRON-native patterns for agents, auth, config-store, and future forwarding to App 9 central.

---

## Quick start (Raspberry Pi or any Docker host)

1. Install **Docker Engine** + **Compose**.
2. Configure `.env` values (Caddy credentials + VOLTTRON branch/ref if needed).
3. From this directory:

   ```bash
   ./rebuild-bas-lite.sh --rebuild-frontend
   ```

4. Browse to **`http://<host-ip>/`** (redirects to **`/app8/`**).

---

## Repo layout

| Path | Purpose |
|------|---------|
| `docker-compose.yml` | **Caddy** + **VOLTTRON runtime** |
| `Dockerfile` | VOLTTRON runtime image build (branch/ref configurable) |
| `docker/volttron/start-volttron.sh` | Idempotent platform + agent bootstrap |
| `docker/caddy/Caddyfile` | Reverse proxy routes |
| `frontend/` | React app; build output synced into `app8_web_agent/webroot` |
| `volttron_data/ben_bacnet/app8_web_agent/` | App 8 VOLTTRON web agent package + config |
| `volttron_data/ben_bacnet/oat_share_agent/` | Optional OAT share supervisory agent |
| `volttron_data/forward_historian/config` | Optional App 9-forwarding hook config |

---

## Branding

Operator chrome stays **BAS Lite** / **BMS Lite** — not Open-FDD product styling.

---

## License

Follow the parent **py-bacnet-stacks-playground** repo license (typically MIT where noted).
