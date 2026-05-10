# Backend

FastAPI backend for the BAS head-end demo. This slice is simulator-backed only; real BACnet drivers remain out of scope and disabled by default.

## Current API surface

This slice exposes the complete implemented backend API for the demo app:

- `GET /health` returns a simple `{"status":"ok"}` readiness check.
- `GET /api/demo/site` returns the seeded BAS hierarchy from `app/demo_data.py`.
- `GET /api/demo/navigation` returns a read-only site/building/floor/equipment summary.
- `GET /api/demo/data-sweep` returns a compact site -> building -> floor -> equipment -> point summary for smoke checks.
- `GET /api/equipment/{equipment_id}` returns one seeded equipment record or `404`.
- `GET /api/equipment/{equipment_id}/points` returns the point list for one seeded equipment record or `404`.
- `GET /api/points/{point_id}` returns one seeded point record with equipment context or `404`.
- `POST /api/auth/login` accepts demo credentials and returns a bearer token plus the user profile.
- `GET /api/auth/me` reads the current demo user from a bearer token.
- `GET /api/schedules` returns the seeded read-only schedule catalog for an authenticated demo user.
- `GET /api/trends/points` returns the seeded trended point catalog.
- `GET /api/trends/samples` returns deterministic simulator trend samples for one or more trended points.
- `GET /api/trends/export.csv` returns the same trend query as CSV.
- `GET /api/alarms/active` returns the seeded active alarm slice.
- `GET /api/alarms/history` returns the resolved alarm history slice.
- `GET /api/alarms/export.csv` returns the active/history alarm slice as CSV.
- `POST /api/alarms/{alarm_id}/ack` acknowledges an active alarm for an authenticated `Operator`, `Engineer`, or `Admin` user.
- `POST /api/alarms/{alarm_id}/shelve` shelves an active alarm for an authenticated `Operator`, `Engineer`, or `Admin` user.
- `POST /api/points/{point_id}/commands` applies a simulator-only command to a commandable point for an authenticated non-`ReadOnly` user.
- `POST /api/points/{point_id}/release` relinquishes a simulator-only command from a commandable point for an authenticated non-`ReadOnly` user.

## Demo credentials

These are demo-only credentials for the in-memory auth slice:

- `admin` / `admin123`
- `operator` / `operator123`
- `readonly` / `readonly123`

## Run

From `/home/ben/bas_app/backend`:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Tests

From `/home/ben/bas_app/backend`:

```bash
pytest
```

## Notes

- The backend data is seeded in `app/demo_data.py`.
- Demo auth state is seeded in `app/auth.py`.
- Command/release state is held in memory in `app/commands.py`.
- Alarm state is held in memory in `app/alarms.py`.
- Schedule catalog data is seeded in `app/demo_data.py` and read through `app/services.py`.
- The frontend shell runs separately from `frontend/`.
- Keep the default demo path simulator-only unless a future checkpoint explicitly adds lab BACnet work.
- There is no real BACnet runtime in this slice; the demo payload is fully in-memory.

## Alarm smoke

With the backend on `0.0.0.0:8000`, an authenticated operator can acknowledge or shelve a seeded active alarm:

```bash
TOKEN=$(curl -sfS -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"operator","password":"operator123"}' \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["access_token"])')

curl -sfS -X POST http://127.0.0.1:8000/api/alarms/alm-sat-high/ack \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"reason":"Checked against occupied schedule"}'

curl -sfS -X POST http://127.0.0.1:8000/api/alarms/alm-light-mismatch/shelve \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"reason":"Shelved during maintenance window"}'

RO_TOKEN=$(curl -sfS -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"readonly","password":"readonly123"}' \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["access_token"])')

curl -sS -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8000/api/alarms/alm-sat-high/ack \
  -H "Authorization: Bearer $RO_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"reason":"ReadOnly users cannot write"}'
```
