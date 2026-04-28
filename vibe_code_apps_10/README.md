# diy-bas

Flask + vanilla JavaScript supervisory UI for BACnet test bench / small BAS supervisory deployments with role-based access and configurable alarm/dashboard tooling.

## What is included

- Flask backend
- vanilla frontend (`app.js`, `dashboard.js`, `schedule.js`, `styles.css`)
- Plotly trend charts (zoom, pan, export image) via CDN
- `config.py` for app and JSON-RPC settings
- `algorithms.py` for shared supervisory helpers
- BACnet discovery via `diy-bacnet-server` JSON-RPC (`client_whois_range`, `client_point_discovery`)
- secure login + role RBAC (`system_integrator`, `building_operator`)
- polling configuration and trend retention in SQLite (WAL mode)
- alarm rule configuration for point types (numeric high/low and boolean mismatch/failure)
- custom dashboard layout storage and device notes for operator overview context
- global logic wire sheet (integrator tab) for input->many output BACnet value sharing
- audit logging for auth, overrides, and configuration changes
- Docker Compose for sibling `diy-bas` + `diy-bacnet-server` containers
- Caddy reverse proxy in front of both services (single entrypoint on port 80)

## Test bench assumptions

- `diy-bacnet-server` is already running on the same network
- the hosted weather points are available on diy-bacnet-server:
  - `web-weather-dry-bulb`
  - `web-weather-relative-humidity`
  - `web-weather-dew-point`
- AHU and VAV both use the shared outside-air temperature reference from diy-bacnet-server

## Local run

```bash
cd ~/diy-bas

sudo apt update
sudo apt install -y python3-full python3-venv

rm -rf .venv
python3 -m venv --copies .venv
. .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

cp -n .env.example .env
export $(grep -v '^#' .env | xargs)

python run.py
```

Open `http://<raspberry-pi-ip>:5050`.

Default bootstrap user (change immediately):
- username: `integrator`
- password: `ChangeMeNow!123`
- maintenance username: `maintenance`
- maintenance password: `ChangeMeNow!123`

Notes:
- If you hit Debian/Raspberry Pi OS externally managed environment errors, the `--copies` venv flow above is the recommended fix.
- The `.env` warning from Flask is non-fatal when you manually export variables.
- `GET/POST /server_hello` on `diy-bacnet-server` does not require auth and is used for connectivity checks.
- Discovery and points metadata are stored in SQLite metadata tables (including `commandable`) for site-agnostic setup.

## Local run (one command bootstrap)

```bash
chmod +x bootstrap_pi.sh
./bootstrap_pi.sh
```

This script:
- installs venv prerequisites,
- rebuilds `.venv` with `--copies`,
- installs requirements,
- loads `.env`,
- optionally imports `BACNET_RPC_API_KEY` from a running `diy-bacnet-server` container.
- prunes stale Docker images older than 30 days by default (`DOCKER_PRUNE_UNTIL=720h`).
- can start the Docker stack with Caddy (`BOOTSTRAP_USE_DOCKER_STACK=1`).
- can auto-restart `diy-bacnet-server` in host-network mode with detected NIC CIDR for BACnet broadcasts.

Optional bootstrap cleanup controls:
- `BOOTSTRAP_DOCKER_CLEANUP=0` to skip Docker cleanup.
- `DOCKER_PRUNE_UNTIL=336h` (example) to change stale-image threshold.
- `BOOTSTRAP_DOCKER_PRUNE_VOLUMES=1` to also prune unused volumes (off by default).
- `BOOTSTRAP_USE_DOCKER_STACK=1` to run `docker compose up -d --build` and serve app at `http://<pi-ip>/`.
- `BOOTSTRAP_MANAGE_BACNET_SERVER=1` to auto-run `diy-bacnet-server` with `--network host` and `--address <nic-cidr>:47808`.
- `DIY_BACNET_BIND_CIDR=<ip>/<prefix>` to override auto-detection (example: `192.168.204.12/24`).

## Windows deploy helper (zip + scp + bootstrap)

From PowerShell on your Windows machine (host/user are required):

```powershell
cd C:\path\to\diy-bas
.\deploy_to_pi.ps1 -PiHost <pi-ip> -PiUser <pi-user> -UseDockerStack $true
```

Optional if your paths are not standard:

```powershell
.\deploy_to_pi.ps1 -PiHost <pi-ip> -PiUser <pi-user> `
  -RemoteDir /home/<pi-user>/diy-bas `
  -RemoteBacnetDir /home/<pi-user>/diy-bacnet-server `
  -UseDockerStack $true
```

Ben is explicitly running this as demonstrated on YouTube.
```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_10\diy-bas
.\deploy_to_pi.ps1 -PiHost 192.168.204.12 -PiUser ben -UseDockerStack $true
```

What it does:
- zips `diy-bas` (excluding `.venv`, caches, local data db files),
- uploads via `scp`,
- unpacks into `/home/ben/diy-bas` on the Pi,
- runs `bootstrap_pi.sh` in setup mode,
- starts Docker stack (Caddy mode by default) and checks `GET /api/health`.

## Docker run

```bash
docker build -t diy-bas .
docker run -d   --name diy-bas   --restart unless-stopped   --env-file .env   -p 5050:5050   diy-bas
```

Open `http://<host-ip>:5050`.

## Docker Compose (recommended)

```bash
docker compose up --build
```

Open `http://127.0.0.1/`.

`diy-bas` will call `diy-bacnet-server` over Docker service DNS using `http://diy-bacnet-server:8080`.
In Pi host-network mode, `diy-bas` talks to `http://host.docker.internal:8080` (configurable with `DIY_BACNET_URL`).

If your `diy-bacnet-server` repo lives somewhere else:

```bash
export DIY_BACNET_SERVER_DIR=/absolute/path/to/diy-bacnet-server
docker compose up --build
```

## Role model

- `system_integrator`
  - full setup/config visibility in left nav
  - can run discovery, edit polling, configure alarms, save dashboard layouts, edit device notes, and schedules
- `building_operator`
  - dashboard/overview + devices + trends + active alarms
  - read-only runtime operations

## Alarm extensions

- Numeric point alarm rule:
  - `pointType: numeric`
  - thresholds: `lowThreshold`, `highThreshold`
  - optional `deadband`
- Boolean point alarm rule:
  - `pointType: bool`
  - expected state: `expectedBool`
  - mismatch delay: `boolDelaySec`

## Useful API routes

- `GET /api/health`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `POST /api/auth/change-password`
- `GET /api/points`
- `POST /api/discovery/whois`
- `POST /api/discovery/device-points`
- `GET /api/discovery/devices`
- `GET /api/polling/config`
- `POST /api/polling/config`
- `GET /api/schedules`
- `POST /api/schedules`
- `GET /api/trends/query`
- `GET /api/diy/schedule`
- `GET /api/algorithms/oat`
- `GET /api/algorithms/test-bench`
- `GET /api/alarm-rules`
- `POST /api/alarm-rules`
- `GET /api/device-notes`
- `POST /api/device-notes`
- `GET /api/dashboard-layouts`
- `POST /api/dashboard-layouts`
- `GET /api/wiresheet/config`
- `POST /api/wiresheet/config`
- `DELETE /api/wiresheet/config/<id>`
- `POST /api/wiresheet/run/<id>`
- `GET /api/wiresheet/status`
- `GET /api/audit/logs` (system integrator only)

## Deployment and persistence notes

- Set `DIY_BAS_SECRET_KEY` in `.env` (bootstrap now generates if missing).
- Set and secure `DIY_BAS_ADMIN_USERNAME` / `DIY_BAS_ADMIN_PASSWORD` in `.env`.
- Set and secure `DIY_BAS_MAINT_USERNAME` / `DIY_BAS_MAINT_PASSWORD` in `.env`.
- Use persistent data directory: `DIY_BAS_DATA_DIR=/var/lib/diy-bas` on Pi.
- `deploy_to_pi.ps1` rotates app code directories but keeps persistent data path outside the release folder.

## SD card friendly defaults (Raspberry Pi)

`diy-bas` defaults to 30-day retention and reduced write frequency for SD-card durability:

- trend retention: `DIY_BAS_TREND_RETENTION_DAYS=30`
- audit retention: `DIY_BAS_AUDIT_RETENTION_DAYS=30`
- app log retention (if file logging enabled): `DIY_BAS_LOG_RETENTION_DAYS=30`
- latest values disk flush interval: `DIY_BAS_LATEST_VALUES_FLUSH_SECONDS=300` (5 min)
  - runtime values are kept in memory and flushed periodically instead of writing every poll tick

Recommended Pi defaults:

- keep `DIY_BAS_LOG_TO_FILE=false` (stdout/container logs only; least SD wear)
- if file logs are required, set:
  - `DIY_BAS_LOG_TO_FILE=true`
  - `DIY_BAS_LOG_LEVEL=INFO`
  - keep 30-day retention unless compliance requires longer

## Logging and audit behavior

- Application logs:
  - always emitted to stdout/stderr
  - optional daily-rotated file logging to `${DIY_BAS_DATA_DIR}/logs/diy-bas.log` when `DIY_BAS_LOG_TO_FILE=true`
  - file log rotation retention controlled by `DIY_BAS_LOG_RETENTION_DAYS`
- Audit logs:
  - persisted in SQLite (`audit_logs` table)
  - defaults to 30-day retention (`DIY_BAS_AUDIT_RETENTION_DAYS`)
  - captures authentication events and user maneuvers:
    - login/logout/password change
    - discovery actions
    - polling config updates
    - schedule updates
    - alarm rule changes
    - device note/layout edits
    - wire sheet rule create/delete/run-now

## Troubleshooting discovery 500 errors

- `POST /api/discovery/whois` now returns detailed diagnostics when BACnet server is offline or auth is invalid.
- Check `GET /api/health` and look at `diy.reachable` + `diy.detail`.
- Common causes:
  - wrong `DIY_BACNET_URL`,
  - missing/invalid `BACNET_RPC_API_KEY`,
  - bacnet server not reachable from Flask runtime.
