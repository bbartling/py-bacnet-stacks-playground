# BAS Lite App 8 Tutorial (Modular VOLTTRON)

App 8 now runs as a Dockerized **modular VOLTTRON** edge stack:

- `volttron` container: ZMQ platform runtime + `platform.driver` + `app8_web_agent`
- `caddy` container: TLS + Basic Auth ingress
- React static files built into `app8_web_agent/webroot` and served from `/app8/`

## 1. Build + run

```bash
./rebuild-bas-lite.sh --rebuild-frontend
```

Windows PowerShell:

```powershell
.\rebuild-bas-lite.ps1 -RebuildFrontend
```

## 2. Validate runtime

```bash
docker compose ps
docker compose logs -f volttron
docker compose exec volttron vctl status
curl -sS http://127.0.0.1:8080/app8/api/health
```

Via Caddy:

- `http://<host>/` (redirects to `/app8/`)
- `https://<host>/app8/`

## 3. BACnet networking fallback

Default compose uses bridge networking + UDP mapping for BACnet. If BACnet/IP broadcast/routing is unreliable on Linux, use host networking override:

```bash
docker compose -f docker-compose.yml -f docker-compose.hostnet.yml up -d
```

## 4. API contract

The React UI expects `/app8/api/*` endpoints from `app8_web_agent`:

- `/app8/api/health`
- `/app8/api/devices`
- `/app8/api/points`
- `/app8/api/setpoints/write`
- `/app8/api/system/metrics`
- `/app8/api/driver/config*`
- `/app8/api/schedule`

## 5. Optional App 9-forward hook

Populate `volttron_data/forward_historian/config` and enable:

```bash
APP8_ENABLE_FORWARDER=1
```

The startup script will install/start `ForwardHistorian` when config is present.
