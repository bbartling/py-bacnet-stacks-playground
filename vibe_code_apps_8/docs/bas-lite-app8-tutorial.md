# BAS Lite App 8 Tutorial

This App 8 stack runs as a Docker deployment with:

- `caddy` edge proxy
- `frontend` static SPA served by nginx
- `api` FastAPI service powered by easy-aso supervisor
- `diy-bacnet` BACnet JSON-RPC backend

If you are setting up a new host, use `docs/BOSS_PI_BAS_LITE_DOCKER.md` as the primary operator runbook.

## BACnet discovery in this stack

Discovery is not performed by a dedicated `/discover` endpoint in `bas_lite_api`.
Runtime BACnet operations are executed through the JSON-RPC backend (`diy-bacnet-server`) and then represented through configured devices/points in supervisor storage.

Practical workflow:

1. Bring up the stack with `docker compose up -d`.
2. Validate the BACnet backend from the host (default published port **`DIY_BACNET_HOST_PORT`**, e.g. `http://127.0.0.1:28090/` — see `.env.example`).
3. Add or import devices/points through the API/UI data model workflow.
4. Confirm values and health through `/app8/api/*` and `/api/v1/*`.

## Project positioning

This project is inspired by platform-style BAS patterns, but it is implemented directly with Docker + easy-aso and does not depend on external platform runtime files.
