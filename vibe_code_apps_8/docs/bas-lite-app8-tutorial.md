# BAS Lite App 8 Tutorial

This App 8 stack runs as a **Docker Compose** deployment with:

- **`caddy`** — edge proxy (TLS + auth optional)
- **`frontend`** — static SPA under **`/app8/`** (nginx; build with **`VITE_BASE_PATH=/app8`** before **`docker compose build frontend`** when using prebuilt **`frontend/dist`** — see **`docker/Dockerfile.frontend`** and **`.env.example`** **`FRONTEND_SKIP_NODE_BUILD`**)
- **`api`** — **`bas_lite_api`** + **easy-aso** supervisor (**PyPI `easy-aso[platform]==0.1.7`**), legacy **`/app8/api/*`** and **`/api/v1/*`**
- **`diy-bacnet`** — BACnet **UDP 47808** + JSON-RPC gateway (single field stack owner)
- **Optional profile `oat`** — **`easy-aso-oat`** lightweight OAT copy loop
- **Optional profile `agents`** — three **`RpcDockedEasyASO`** sidecars (**OAT share**, **GL36 VAV requests**, **GL36 AHU SAT reset**) via **`easy-aso-agent run`**

If you are setting up a new host, use **`docs/BOSS_PI_BAS_LITE_DOCKER.md`** as the primary operator runbook (Git clone on the Pi + **`scripts/bootstrap-bas-lite.sh`**).

## BACnet discovery in this stack

Discovery is not performed by a dedicated `/discover` endpoint in `bas_lite_api`.
Runtime BACnet operations are executed through the JSON-RPC backend (`diy-bacnet-server`) and then represented through configured devices/points in supervisor storage.

Practical workflow:

1. Bring up the stack with `docker compose up -d`.
2. Validate the BACnet backend from the host (default published port **`DIY_BACNET_HOST_PORT`**, e.g. `http://127.0.0.1:28090/` — see `.env.example`).
3. Add or import devices/points through the API/UI data model workflow.
4. Confirm values and health through `/app8/api/*` and `/api/v1/*`.

## Project positioning

BAS Lite is intentionally compact: **Docker Compose**, the **easy-aso** supervisor + FastAPI surfaces, **diy-bacnet** JSON-RPC, and the React operator UI. Driver JSON and SQLite state ship in the **`bas_lite_data`** volume. **Multi-agent** supervisory loops live in **optional** Compose services under profile **`agents`** (three stock **`RpcDockedEasyASO`** agents + optional merge from **`docker-compose.easy-aso-agents.example.yml`**), sharing the same JSON-RPC gateway as the API — no second BACnet **UDP 47808** bind. Profile **`oat`** adds the legacy **easy-aso-oat** helper. Prefer config JSON (**`EASY_ASO_GL36_*`**, **`OAT_*`**) over forked core library code for new buildings.
