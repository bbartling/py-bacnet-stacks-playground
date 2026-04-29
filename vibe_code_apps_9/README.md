# Week 9 - diy-bas Beginner Guide

This README is a beginner walkthrough for `vibe_code_apps_9/diy-bas-primitive`: what files do what, how deploy works, how users are configured, where data lives, and how to keep a Raspberry Pi SD card healthy.

## 1) What is in this folder

- app root: `diy-bas-primitive`
- Pi bootstrap script: `diy-bas-primitive/bootstrap_pi.sh`
- Windows deploy script: `diy-bas-primitive/deploy_to_pi.ps1`
- environment template: `diy-bas-primitive/.env.example`

## 2) How the system fits together (simple)

- Flask backend serves APIs and the vanilla JS frontend.
- Caddy (in Docker mode) fronts the app on port 80.
- `diy-bas` calls `diy-bacnet-server` for BACnet reads/writes.
- Runtime/trend data is persisted under `/var/lib/diy-bas` on Pi.

## 3) Quick local run (Windows + Docker)

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_9\diy-bas-primitive
copy .env.example .env
docker compose up --build
```

Open:
- `http://127.0.0.1/` (through Caddy)
- `http://127.0.0.1:5050/` (direct Flask, if exposed)

## 4) Deploy to Raspberry Pi (from Windows)

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_9\diy-bas-primitive
.\deploy_to_pi.ps1 -PiHost <pi-ip> -PiUser <pi-user> -UseDockerStack $true
```

What deploy does:
- stages and zips project files
- uploads with `scp`
- rotates old release to `.bak`
- ensures `/var/lib/diy-bas` exists
- runs `bootstrap_pi.sh` in setup mode
- starts services and checks `/api/health`

Useful options:
- `-RunBootstrap $false` upload only
- `-StartApp $false` stage + bootstrap only
- `-UseDockerStack $false` run in venv mode
- `-RemoteDir /home/<user>/diy-bas`
- `-RemoteBacnetDir /home/<user>/diy-bacnet-server`

## 5) User setup env vars (integrator + maintenance)

`bootstrap_pi.sh` ensures these exist in `.env`:

- `DIY_BAS_ADMIN_USERNAME=integrator`
- `DIY_BAS_ADMIN_PASSWORD=ChangeMeNow!123`
- `DIY_BAS_MAINT_USERNAME=maintenance`
- `DIY_BAS_MAINT_PASSWORD=ChangeMeNow!123`

Change all default passwords immediately after first boot.

## 6) Auth + cookie session notes

Important status for this specific `diy-bas-primitive` codebase:

- The env variables for auth and cookie/session are present in `.env.example`.
- This primitive app currently does **not** yet include full login/session enforcement code (`/api/auth/*`, Flask-Login guards).
- Cookie-related env values are already documented for the auth-enabled build path:
  - `DIY_BAS_SESSION_HOURS=24`
  - `DIY_BAS_SESSION_COOKIE_SECURE=false` (set `true` behind HTTPS)
  - `DIY_BAS_SESSION_COOKIE_SAMESITE=Lax`
  - `DIY_BAS_SESSION_REFRESH_EACH_REQUEST=true`

When auth-enabled app code is merged in, those settings control session-cookie behavior and default 24-hour lifetime.

## 7) Where data is stored

- Persistent app data directory on Pi: `/var/lib/diy-bas`
- Typical data includes discovery files, schedules, latest values, and trends DB files.
- In this primitive version, several runtime artifacts are JSON files plus trend DB storage.

## 8) SD-card-friendly settings (to reduce wear)

Defaults now favor Pi longevity:

- `DIY_BAS_TREND_RETENTION_DAYS=30`
- `DIY_BAS_AUDIT_RETENTION_DAYS=30`
- `DIY_BAS_LOG_RETENTION_DAYS=30`
- `DIY_BAS_LATEST_VALUES_FLUSH_SECONDS=300` (less frequent writes)
- `DIY_BAS_LOG_TO_FILE=false` (prefer stdout/container logs to reduce SD writes)

If you must write file logs, keep retention modest and consider external storage.

## 9) New-user checklist (recommended)

1. Copy `.env.example` to `.env`.
2. Set strong passwords for integrator and maintenance users.
3. Set `DIY_BAS_SECRET_KEY` to a long random value.
4. Keep `DIY_BAS_LOG_TO_FILE=false` unless required.
5. Run deploy script and confirm `/api/health`.
6. Log in (if auth-enabled build is in use) and verify both roles.

## 10) If scripts disappear again after refactor

Re-add these files first:
- `diy-bas-primitive/bootstrap_pi.sh`
- `diy-bas-primitive/deploy_to_pi.ps1`
- `diy-bas-primitive/.env.example`

Then re-run the deploy command in section 4.