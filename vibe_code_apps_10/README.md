# diy-bas (vibe stack)

This folder (`vibe_code_apps_10`) holds the **diy-bas** supervisory app: **Django** + **Gunicorn** serving a vanilla JS front end (`app.js`, `dashboard.js`, `schedule.js`, `styles.css`). Source lives in **`diy-bas/`** (project root `diybas/`, app code under `bas/` and `app/`).

## What is included

- Django REST-style JSON APIs under `/api/*` (session auth + RBAC)
- SQLite (`data/trends.sqlite3`) for devices, points, polling, alarm rules, trend samples, **alarm audit** (`alarm_events`), audit logs
- JSON files in `data/` for schedules, notifications, latest BACnet values, wiresheet cache, etc.
- BACnet discovery and reads via `diy-bacnet-server` JSON-RPC
- Roles: `system_integrator` vs `building_operator` (and Django `BasRole` / maintenance where configured)
- **Sidebar (integrator):** **Building & operations** (black/neutral nav) vs **System integrator** (green nav); first integrator tab is **Discovery**, then Devices, Points, Wire sheet, Custom dashboard
- Plotly trends, SSE live trend stream (`/api/trends/stream`), points bulk polling & split alarm modals (threshold vs cross-point vs device-offline timing)
- Caddy + Docker Compose entry on port **80** (recommended on Pi); Gunicorn WSGI inside `diy-bas` container

## Django for BAS technicians

If you commission BACnet for a living, you already think in **objects**, **points**, **graphics**, **alarms**, **schedules**, and **users**. **Django** is a Python **web application framework**: it gives you a structured way to ship those ideas as a secure browser app plus JSON APIs, with a large standard library of “batteries included” features so you do not reinvent plumbing.

### Mental model: where BAS concepts live in Django

| Familiar BAS idea | Rough Django / diy-bas mapping |
| --- | --- |
| Alarm definition (limits, delays, comparisons) | Rows in SQLite `alarm_rules` (saved via `POST /api/alarm-rules`); runtime such as “last good poll per device” in `data/alarm_runtime.json` |
| Alarm annunciator / history | `alarm_events` table + `/api/alarms/events` |
| Point list / metadata | `discovered_points` + merged polling config |
| Schedules, notifications, latest values | JSON documents under `data/` (schedules are still “site configuration” like a JACE archive) |
| Integrator vs operator | Django auth user + `UserProfile.bas_role` (RBAC checked in views) |

Django projects are organized into **apps** (e.g. `bas/` for HTTP views and templates, `app/` for BACnet-facing services). A **model** (Django’s ORM class) is like a **record type** in a controller: one table, one responsibility. diy-bas uses **both** Django models (users/profiles) and **plain SQLite** tables in `app/trend_store.py` for high-volume trend and alarm data—same idea, less ORM overhead for samples.

### How this app hangs together

1. **Browser** loads static JS (`dashboard.js`) and calls `/api/*` with the session cookie.
2. **Django views** (`bas/views.py`) authenticate the user, read/write SQLite or JSON, and call **BACnet RPC** where needed.
3. **Alarm engine** (`app/alarm_engine.py`) runs when live values refresh: threshold rules, optional **point-vs-point** (`rule_kind: cross_compare`), and **device offline** if no successful read for `deviceOfflineSec` on any polling-enabled device instance.

### “Batteries included” Django features you can grow into for a BAS

These ship with or alongside Django and map cleanly to building automation products:

- **Auth & sessions** — operator logins, integrator-only screens, session timeout (already used for the dashboard).
- **Password validation & password change flows** — same patterns as corporate IT; can enforce complexity and rotation policies.
- **Email backend (SMTP)** — alarm email dial-out, digest summaries, or “device offline” notifications without a separate mailer service in the first iteration.
- **Password reset by email** — built-in views and tokens; useful for forgotten integrator passwords on a customer site.
- **Admin site** (`/admin/`) — quick CRUD on users, profiles, or future “site config” models without building a custom UI.
- **Forms & CSRF protection** — server-side validation for any future HTML forms; APIs use session/JSON patterns with `@csrf_exempt` only where intentional.
- **Internationalization / time zones** — localize operator-facing strings and timestamps per building.
- **Caching framework** — reduce SQLite or RPC load for heavy graphics pages.
- **Management commands** — one-off imports, backups, BACnet object exports (`python manage.py …`), like running a script on a JACE shell but reproducible.
- **Migrations** — versioned schema changes for anything stored in Django’s ORM (SQLite/Postgres in production).
- **Static file handling & security middleware** — HTTPS headers, clickjacking protection, MIME safety for operator kiosks.
- **Task queues (Celery / RQ, common add-on)** — async alarm routing to SMS/pager/Teams, long BACnet batch jobs, or report generation without blocking the web worker.

None of these require abandoning BACnet—they sit **above** the field stack as supervisory glue, the same role Niagara, Distech, or vendor portals play today.

## Test bench assumptions

- `diy-bacnet-server` is already running on the same network
- the hosted weather points are available on diy-bacnet-server:
  - `web-weather-dry-bulb`
  - `web-weather-relative-humidity`
  - `web-weather-dew-point`
- AHU and VAV both use the shared outside-air temperature reference from diy-bacnet-server

## Local run (Django)

```bash
cd ~/path/to/vibe_code_apps_10/diy-bas

sudo apt update
sudo apt install -y python3-full python3-venv

rm -rf .venv
python3 -m venv --copies .venv
. .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

cp -n .env.example .env
export $(grep -v '^#' .env | xargs)

python manage.py migrate
python manage.py runserver 0.0.0.0:5050
```

Open `http://<raspberry-pi-ip>:5050` (or use Docker Compose + Caddy on port 80 per below).

Default bootstrap user (change immediately):
- username: `integrator`
- password: `ChangeMeNow!123`
- maintenance username: `maintenance`
- maintenance password: `ChangeMeNow!123`

**How to log in:** Open the app in your browser (for example `http://127.0.0.1/` with Docker Compose + Caddy, or `http://<host>:5050` if you hit Django directly). The first screen is the login form. Use the **integrator** or **maintenance** username and password above unless you changed them in `.env` (`DIY_BAS_ADMIN_*` and `DIY_BAS_MAINT_*`). After a successful login, Django keeps you signed in with a **session cookie** (default lifetime **24 hours**, see `DIY_BAS_SESSION_*` in `.env.example`).

**Debugging blank dashboard tabs:** the browser console shows `[diy-bas][dash] paint` with `route`, `devices`, and `points` counts after each paint, and `[diy-bas][tab] navigate` when the dashboard route changes. If you open **Schedule** first, the shell still syncs the hidden dashboard route to `schedule` so logs stay aligned with the sidebar.

Notes:
- If you hit Debian/Raspberry Pi OS externally managed environment errors, the `--copies` venv flow above is the recommended fix.
- The `.env` warning from Django is non-fatal when you manually export variables.
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
- runs `docker compose down` in the previous install (when present), then removes `diy-bas.bak` with **`sudo rm -rf`** when needed so root-owned `data/` from Docker does not block deploy,
- unpacks into `/home/ben/diy-bas` on the Pi,
- runs `bootstrap_pi.sh` in setup mode,
- starts Docker stack (Caddy mode by default) and checks `GET /api/health`,
- runs **`POST /api/auth/login`** on the Pi using `DIY_BAS_ADMIN_*` from the remote `.env` (skip with `-TestLogin:$false` if you use passwordless-sudo restrictions or a custom check).

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
  - **Building & operations** nav: overview, trends, alarms, notifications, schedule, docker logs (black styling)
  - **System integrator** nav: discovery, devices, points, wire sheet, custom dashboard (green styling)
- `building_operator`
  - overview, devices, alarms, trends (and docker logs when `basRole` is maintenance)
  - read-only runtime operations where enforced server-side

## Alarm extensions

- **Threshold (default `rule_kind: threshold`)** — numeric high/low + `deadband`, or binary `expectedBool`; **`delay_sec` / `boolDelaySec`** hold time in seconds before opening (per condition in the engine).
- **Cross-point (`rule_kind: cross_compare`)** — `compare_point_id` = point B, `compare_operator` `eq` or `ne`; alarms on relationship violation after the same delay fields.
- **Device offline** — synthetic alarm `point_id` like `device:<instance>` with `kind: device_offline` when no **successful** BACnet read is seen for that device instance for longer than **`deviceOfflineSec`** (default **300**, clamped **60–86400**). Attempts are tracked per read-now batch; success timestamps live in `data/alarm_runtime.json`. Configure via **`GET/POST /api/alarm-settings`** (`{ "deviceOfflineSec": 300 }` on POST; integrator-only write).
- UI: **Points** tab exposes separate modals for threshold/binary vs cross-point vs device-offline timing.

## Useful API routes (Django diy-bas)

- `GET /api/health`
- `POST /api/auth/login` · `POST /api/auth/logout` · `GET /api/auth/me` · `POST /api/auth/token`
- `GET /api/points` (merged live values + alarm flags)
- `GET /api/devices` · `DELETE /api/devices/<id>`
- `POST /api/discovery/whois` · `POST /api/discovery/device-points` · `GET /api/discovery/devices`
- `GET/POST /api/polling/config` · `POST /api/polling/read-now`
- `GET/POST /api/schedules` (JSON document; POST also pushes active profile to BACnet when RPC succeeds)
- `GET /api/trends/query` · `GET /api/trends/stream` (SSE)
- `GET /api/alarms/events` (active + history)
- `GET/POST /api/alarm-rules` (POST body may be `{ "items": [ … ] }` for batch; rules may include `ruleKind`, `comparePointId`, `compareOperator`, `delaySec`)
- `GET/POST /api/alarm-settings` (`deviceOfflineSec`; POST integrator-only)
- `GET/POST /api/device-notes`
- `GET/POST /api/dashboard-layouts`
- `GET/POST /api/wiresheet/config` · …
- `DELETE /api/wiresheet/config/<id>`
- `POST /api/wiresheet/run/<id>`
- `GET /api/wiresheet/status`
- `GET /api/audit/logs` (system integrator only)

## Deployment and persistence notes

- Set `DIY_BAS_SECRET_KEY` in `.env` (bootstrap now generates if missing).
- Set and secure `DIY_BAS_ADMIN_USERNAME` / `DIY_BAS_ADMIN_PASSWORD` in `.env`.
- Set and secure `DIY_BAS_MAINT_USERNAME` / `DIY_BAS_MAINT_PASSWORD` in `.env`.
- Use persistent data directory: `DIY_BAS_DATA_DIR=/var/lib/diy-bas` on Pi **when running Django directly on the host** (venv / `gunicorn` or `runserver`).
- **Docker Compose** forces `DIY_BAS_DATA_DIR=/app/data` for the `diy-bas` service so SQLite always lives on the bind-mounted `./data` folder next to the compose file (do not expect `/var/lib/diy-bas` inside the container unless you add a matching volume).
- `deploy_to_pi.ps1` rotates app code directories but keeps persistent data path outside the release folder.

## Troubleshooting login and `.env` on the Pi

### `./.env: line 19: user: No such file or directory`

That message comes from **bash** when `bootstrap_pi.sh` runs `. ./.env`. If a line contains angle brackets, bash treats `<user>` as **input redirection** (read from a file named `user`), not as a placeholder.

- **Fix:** In `.env`, set a real path, for example `DIY_BACNET_SERVER_DIR=/home/ben/diy-bacnet-server`. Never use `/home/<user>/...` in a file that gets sourced by bash.

### Login fails but health works

Users and password hashes live in **SQLite** (`trends.sqlite3` under the app data directory). On first run the app creates missing users from `DIY_BAS_ADMIN_*` and `DIY_BAS_MAINT_*`. **Changing `.env` later does not change existing hashes** unless you turn on refresh or reset the DB.

- **Use the same credentials as in your Pi’s `.env`**, not an old copy of `.env.example`, unless they match.
- Set **`DIY_BAS_BOOTSTRAP_REFRESH_PASSWORDS=true`** in `.env` (default in `.env.example`) so integrator/maintenance passwords are **re-applied from `.env` on every start** while that flag stays true. Set it to **`false`** after passwords are stable and you rely on the in-app change-password flow.
- After fixing `docker-compose.yml` to load `.env` into the container, run **`docker compose up -d --build`** again.
- Quick check from the Pi: `curl -s -X POST http://127.0.0.1/api/auth/login -H 'Content-Type: application/json' -d '{"username":"integrator","password":"ChangeMeNow!123"}'` (adjust user/password to match `.env`).

### `poll loop error: unable to open database file`

Usually the app cannot create or open `trends.sqlite3` under the configured data directory (permissions, missing directory, or wrong path inside Docker).

- **Docker:** ensure the compose file keeps SQLite on `./data:/app/data` and that `DIY_BAS_DATA_DIR` inside the container is `/app/data` (compose now forces this so it does not inherit `/var/lib/diy-bas` from the host `.env` by mistake).
- On the Pi host: `ls -la ~/diy-bas/data` and ensure the user running Docker can write there (often `chmod`/`chown` on `data/` after a restore).

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
