# diy-bas

Flask + vanilla JavaScript supervisory UI for BACnet test bench / small BAS supervisory deployments.

## What is included

- Flask backend
- vanilla frontend (`app.js`, `dashboard.js`, `schedule.js`, `styles.css`)
- `config.py` for app and JSON-RPC settings
- `algorithms.py` for shared supervisory helpers
- BACnet discovery via `diy-bacnet-server` JSON-RPC (`client_whois_range`, `client_point_discovery`)
- polling configuration and 2-week trend retention in SQLite (WAL mode)
- Docker Compose for sibling `diy-bas` + `diy-bacnet-server` containers

## Test bench assumptions

- `diy-bacnet-server` is already running on the same network
- the hosted weather points are available on diy-bacnet-server:
  - `web-weather-dry-bulb`
  - `web-weather-relative-humidity`
  - `web-weather-dew-point`
- AHU and VAV both use the shared outside-air temperature reference from diy-bacnet-server

## Local run

```bash
cp .env.example .env
export $(grep -v '^#' .env | xargs)
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:5050`.

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

Open `http://127.0.0.1:5050`.

`diy-bas` will call `diy-bacnet-server` over Docker service DNS using `http://diy-bacnet-server:8080`.

## Useful API routes

- `GET /api/health`
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

## Notes

This package does **not** include user auth.
