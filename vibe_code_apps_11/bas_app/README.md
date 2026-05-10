# BAS app scaffold

Initial scaffold for the BAS supervisory head-end application.

## Layout

- `backend/` - Python API and simulator services.
- `frontend/` - BAS workstation SPA shell.

## Current runnable slice

The backend now exposes a minimal FastAPI service with a demo BAS hierarchy and simulator-backed point values.
The frontend now has a BAS workstation shell that matches the dark `graphic.html` palette and pulls live navigation summary data from the backend, with a visible degraded state if the API is unavailable.
The backend now also serves read-only navigation and equipment lookup endpoints for the seeded demo site.
The frontend now also renders a live equipment point table from `/api/equipment/{equipment_id}/points` for the primary seeded equipment.
The backend now also exposes demo login and `GET /api/auth/me` bearer-token auth with seeded credentials (`admin` / `admin123`, `operator` / `operator123`, `readonly` / `readonly123`).
The frontend login box is wired to those auth endpoints and shows the current demo user/role in the header and sidebar.
The backend now also records in-memory audit events for login success and failure and exposes `GET /api/audit/events`; the frontend shows a compact recent-audit panel for those login events.
The backend now also exposes protected `GET /api/schedules` with four seeded category buckets (`air_side_occupancy`, `ventilation_doas`, `terminal_zone_setback`, `lighting_ancillary`), and the frontend shows a compact read-only schedule catalog after sign-in.
The backend now also exposes simulator-only point command and release endpoints for authenticated `Operator`, `Engineer`, or `Admin` users, and the point detail payload shows commanded/overridden state when active.
The frontend point detail panel now includes a compact command/release workflow that stays disabled for unauthenticated and ReadOnly users.
The backend now also exposes read-only trend history endpoints for seeded trended points, including CSV export.
The frontend now also includes a compact trends panel with point selection, range selection, and CSV export.
The backend now also exposes read-only alarm list, history, and CSV export endpoints seeded from the demo equipment and points.
The backend now also exposes protected alarm acknowledge/shelve workflows for authenticated operator roles, and the frontend shows a compact active/history alarm panel with CSV export.
The backend now also exposes `GET /api/demo/data-sweep`, and the repo includes a one-shot `scripts/data_sweep.sh` smoke that proves the seeded site -> building -> floor -> equipment -> point path.

### Backend run

From `/home/ben/bas_app/backend`:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The post-wake stack hook keeps the backend and frontend bound to `0.0.0.0:8000` and `0.0.0.0:5173` between wakes. It also checks `http://127.0.0.1:8000/api/demo/navigation` so a stale backend on `:8000` is restarted before the wake finishes. Set `POST_WAKE_STACK_RESTART=true` in `cron_codex/.env` when you want each wake to force a fresh restart instead of only reusing healthy listeners.

### Backend tests

From `/home/ben/bas_app/backend`:

```bash
pytest
```

### Frontend run

From `/home/ben/bas_app/frontend`:

```bash
python3 -m http.server 5173 --bind 0.0.0.0
```

### Dial-in from another PC (BAS workstation style)

#### Rule so this does not bite you again

| Where the browser runs | What `http://localhost:5173/` means |
|-------------------------|-------------------------------------|
| **On bensserver** (or SSH port-forward to it) | “This **server**” — only works if `http.server` is listening **on that same machine**. |
| **On your laptop / tablet** | “**This laptop**” — **not** bensserver. There is usually **no** BAS app there, so the page will be empty, refuse connection, or show some unrelated local app. |

**Remote operators must use the server’s LAN IP (or DNS name), never `localhost`:**

- **UI:** `http://<server-lan-ip>:5173/`
- **API:** `http://<server-lan-ip>:8000/` (the static shell already points at **:8000** when you load the UI from **:5173**)

**Make it habitual:** bookmark **`http://192.168.204.18:5173/`** (replace with your real IP). Optionally add a name on your laptop’s **`/etc/hosts`** (e.g. `bas-headend  192.168.204.18`) and use **`http://bas-headend:5173/`** so you never think “localhost.”

Your **head-end UI** is meant to be opened as **`http://<server-lan-ip>:5173/`** (not plain **`http://<ip>/`** on port 80 — that is often a **different** service such as Caddy).

From the server, a quick check:

```bash
curl -sfS "http://$(hostname -I | awk '{print $1}'):8000/health"
curl -sfS -o /dev/null -w '%{http_code}\n' "http://$(hostname -I | awk '{print $1}'):5173/"
```

If that works on the server but **not** from your laptop, open **TCP 8000** and **5173** in the server firewall (e.g. `ufw allow …`) and avoid guest Wi‑Fi client isolation.

#### Port 80 / Caddy (old apps on the same host)

If **`http://<ip>/`** shows some **other** login or site, that is **Caddy (or nginx) on port 80**, not this BAS static server. You can:

1. **Stop Caddy so nothing owns :80** (until you reboot or start it again):

   ```bash
   sudo systemctl stop caddy
   ```

   To leave it off across reboots: `sudo systemctl disable caddy` (only if you really do not need it).

2. **Keep Caddy but repoint it** at this head-end: use **`deploy/Caddyfile.example`** as a template so **`/`** → **`127.0.0.1:5173`** and **`/api`**, **`/health`**, **`/docs`**, … → **`127.0.0.1:8000`**, then `sudo systemctl reload caddy`. Remove or comment out **conflicting `http://…` site blocks** in your real Caddyfile so only one app answers that host.

3. **Do not** “kill random processes” on port 80 — use **systemctl** (or your orchestrator) so you do not break unrelated services.

**Single URL on port 80 (optional):** after Caddy proxies as in (2), open **`http://<ip>/`** only; the frontend uses **same-origin** API (no **:8000** in the browser) when you are **not** on port **5173**.

### Smoke check

With the backend on `0.0.0.0:8000` and the frontend on `0.0.0.0:5173`, run:

```bash
curl -sfS http://127.0.0.1:8000/health &&
curl -sfS http://127.0.0.1:8000/api/demo/navigation &&
curl -sfS http://127.0.0.1:8000/api/equipment/eq-ahu-1 &&
curl -sfS http://127.0.0.1:8000/api/points/pt-sat &&
curl -sfS http://127.0.0.1:8000/api/trends/points &&
curl -sfS 'http://127.0.0.1:8000/api/trends/samples?point_ids=pt-sat,pt-sa-sp&hours=4' &&
curl -sfS 'http://127.0.0.1:8000/api/trends/export.csv?point_ids=pt-sat,pt-sa-sp&hours=4' &&
curl -sfS http://127.0.0.1:8000/api/alarms/active &&
curl -sfS http://127.0.0.1:8000/api/alarms/history &&
curl -sfS http://127.0.0.1:8000/api/alarms/export.csv &&
curl -sfS -X POST http://127.0.0.1:8000/api/auth/login -H 'Content-Type: application/json' -d '{"username":"operator","password":"operator123"}' &&
curl -sfS http://127.0.0.1:8000/api/demo/data-sweep &&
TOKEN=$(curl -sfS -X POST http://127.0.0.1:8000/api/auth/login -H 'Content-Type: application/json' -d '{"username":"operator","password":"operator123"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])') &&
curl -sfS -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/schedules &&
curl -sfS http://127.0.0.1:5173/
```

### Data sweep smoke

From `/home/ben/bas_app`:

```bash
/home/ben/bas_app/scripts/data_sweep.sh
```

Expected success output:

```text
data sweep ok: site-1 -> bldg-1 -> floor-1 -> eq-ahu-1 -> pt-sa-sp
```

### Schedule bucket smoke

From `/home/ben/bas_app`:

```bash
/home/ben/bas_app/scripts/check_schedules.sh
```

Expected success output:

```text
schedule buckets ok: air_side_occupancy -> ventilation_doas -> terminal_zone_setback -> lighting_ancillary; weekly/exception data present
```

### Browser / manual frontend sweep

Use this when you want to verify the current static frontend without adding Playwright or other browser tooling.

1. Start the backend on `0.0.0.0:8000` and the frontend on `0.0.0.0:5173` using the commands above.
2. Open `http://<host-ip>:5173/` in a browser.
3. Log in with the demo credentials for `operator` or `admin`.
4. Expand the navigation tree and confirm the path `Site -> Building -> Floor -> Equipment -> Points` is visible.
5. Open the seeded AHU equipment, then open one point detail row and confirm live simulator-backed values render in the point panel.
6. Open an active alarm row and use the `Point` and `Equipment` buttons.
7. Confirm the target point/equipment panel visibly scrolls or focuses into view.
8. Open the browser devtools console and confirm there are no `error`-level messages during that path.
9. Record the result as a pass only if the alarm buttons visibly land on the related panel and the console stays free of `error` entries.

### Auth and audit smoke examples

```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"operator","password":"wrong"}'

TOKEN=$(curl -sfS -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"operator","password":"operator123"}' \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["access_token"])')

curl -sfS http://127.0.0.1:8000/api/auth/me -H "Authorization: Bearer $TOKEN"
curl -sfS http://127.0.0.1:8000/api/audit/events
curl -sfS http://127.0.0.1:8000/api/schedules -H "Authorization: Bearer $TOKEN"

curl -sfS -X POST http://127.0.0.1:8000/api/points/pt-sa-sp/commands \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"value":56.5,"reason":"Commissioning test","confirmed":true}'

curl -sfS -X POST http://127.0.0.1:8000/api/points/pt-sa-sp/release \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"reason":"Return to schedule"}'
```

### URLs

- Health: `http://<host-ip>:8000/health`
- Demo site: `http://<host-ip>:8000/api/demo/site`
- Demo navigation: `http://<host-ip>:8000/api/demo/navigation`
- Equipment detail: `http://<host-ip>:8000/api/equipment/eq-ahu-1`
- Equipment points: `http://<host-ip>:8000/api/equipment/eq-ahu-1/points`
- Demo login: `http://<host-ip>:8000/api/auth/login`
- Authenticated me: `http://<host-ip>:8000/api/auth/me`
- Audit events: `http://<host-ip>:8000/api/audit/events`
- Schedules: `http://<host-ip>:8000/api/schedules`
- Trend points: `http://<host-ip>:8000/api/trends/points`
- Trend samples: `http://<host-ip>:8000/api/trends/samples?point_ids=pt-sat,pt-sa-sp&hours=4`
- Trend CSV export: `http://<host-ip>:8000/api/trends/export.csv?point_ids=pt-sat,pt-sa-sp&hours=4`
- Alarm active list: `http://<host-ip>:8000/api/alarms/active`
- Alarm history: `http://<host-ip>:8000/api/alarms/history`
- Alarm CSV export: `http://<host-ip>:8000/api/alarms/export.csv`
- Point command: `http://<host-ip>:8000/api/points/pt-sa-sp/commands`
- Point release: `http://<host-ip>:8000/api/points/pt-sa-sp/release`
- Frontend shell: `http://<host-ip>:5173/`

Open `index.html` in a browser or use the HTTP server above to view the shell.
