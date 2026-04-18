# BAS Lite (vibe_code_apps_8)

Dashboard + weekly schedule editor (vanilla HTML/CSS/JS), optional **Flask supervisor** with JSON file storage and JSON-RPC to [diy-bacnet-server](https://github.com/bbartling/diy-bacnet-server).

---

## Run locally (vanilla only)

The demo in `vannila/` is plain HTML/CSS/JS. Serve it with Python’s built-in HTTP server (stdlib only, no Node):

```bash
python vannila/serve.py
```

Run from the `vibe_code_apps_8` directory (or adjust paths). Open the URL printed in the terminal (default `http://127.0.0.1:8080/`).

Optional environment variables: `PORT` (default `8080`), `BIND` (default `127.0.0.1`). Example — PowerShell: `$env:PORT='9000'; python vannila/serve.py`

For the separate React/Vite app under `react/`, see `react/README.md`.

---

## Docker on Raspberry Pi (supervisor + diy-bacnet-server)

Use this when you want the **Flask UI + `/api` + WebSocket** served from Docker, alongside the **diy-bacnet** container from [bbartling/diy-bacnet-server](https://github.com/bbartling/diy-bacnet-server) (see its [Dockerfile](https://github.com/bbartling/diy-bacnet-server/blob/master/Dockerfile): BACnet **UDP 47808**, HTTP **5000** in the image).

### 1. Directory layout

Put **diy-bacnet-server** next to **vibe_code_apps_8** under the same parent folder (so the default compose build path works):

```text
your-edge-folder/
  diy-bacnet-server/          # git clone https://github.com/bbartling/diy-bacnet-server.git
  py-bacnet-stacks-playground/   # this monorepo (or only copy vibe_code_apps_8)
    vibe_code_apps_8/         # Dockerfile + docker-compose.yml live here
```

If your diy clone lives somewhere else, set **`DIY_BACNET_REPO`** to that directory when calling compose (absolute path is safest).

### 2. Bearer token (required for JSON-RPC auth)

diy-bacnet-server uses **`BACNET_RPC_API_KEY`**: when set, protected routes require `Authorization: Bearer <key>` (see [environment.md](https://github.com/bbartling/diy-bacnet-server/blob/master/docs/environment.md) in the diy repo).

Use the **same** secret for both services:

1. Copy `vibe_code_apps_8/.env.example` to **`vibe_code_apps_8/.env`**.
2. Set **`BACNET_RPC_API_KEY`** to a long random string.
3. `docker compose` loads `.env` automatically from the same folder as `docker-compose.yml`.

The supervisor reads **`BACNET_RPC_API_KEY`** and sends the Bearer header on every JSON-RPC call (e.g. `server_update_schedule`).

### 3. Build and run (both containers)

On the Pi, from **`vibe_code_apps_8/`**:

```bash
cp .env.example .env
# edit .env — set BACNET_RPC_API_KEY

docker compose up --build
```

- **Supervisor UI:** `http://<pi-ip>:5050/` (or `http://127.0.0.1:5050` on the Pi itself).
- **diy JSON-RPC / OpenAPI:** HTTP on **port 5000** on the host (per upstream image).
- **BACnet/IP:** UDP **47808** on the host.

`docker-compose.yml` uses **`network_mode: host`** for both services so BACnet broadcasts and `DIY_BACNET_URL=http://127.0.0.1:5000` behave like the upstream quick-start. **Host networking is Linux-oriented** (typical on Raspberry Pi OS). On Docker Desktop for Windows/macOS, host networking behaves differently; use a Linux Pi or a Linux VM for field-realistic tests.

### 4. Schedule object name

Your diy **CSV** must define a **Schedule** whose **`Name`** matches **`DIY_SCHEDULE_OBJECT_NAME`** (default `WeeklyOccupancy`). Override in `.env`:

```bash
DIY_SCHEDULE_OBJECT_NAME=YourScheduleName
```

### 5. Persist supervisor JSON

Compose mounts the named volume **`supervisor_data`** at **`/data`** in the supervisor container (`schedules.json`, `notifications.json`, etc.). To reset learning data, remove the volume: `docker compose down -v` (destructive).

### 6. Run only the supervisor image (diy already running)

If diy is already on the host (native or another compose stack) on port 5000:

```bash
cd vibe_code_apps_8
docker build -t bas-supervisor .
docker run --rm --network host \
  -e BACNET_RPC_API_KEY="same-secret-as-diy" \
  -e DIY_BACNET_URL=http://127.0.0.1:5000 \
  -v bas-supervisor-data:/data \
  bas-supervisor
```

---

## Run locally (Flask supervisor, no Docker)

From `vibe_code_apps_8/supervisor_flask/`:

```bash
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5050/`. Defaults assume diy’s HTTP API on **`http://127.0.0.1:5000`** (see the [diy Dockerfile](https://github.com/bbartling/diy-bacnet-server/blob/master/Dockerfile) `EXPOSE 5000`). Override with **`DIY_BACNET_URL`** if your run uses another port ([published docs](https://bbartling.github.io/diy-bacnet-server/)).

---

## UI behaviour (schedule)

- **Schedule** — Top dropdown (**Select schedule**). The read-only **Weekly calendar** and **Operating week** table reflect the active schedule.
- **Operating week** — **No schedule** = off for that weekday; otherwise **Start** / **Stop**.
- **Holidays** — Multi-select or range, then add; optional **Unoccupied** per holiday row.
- **BACnet points** — Stored per schedule profile.
- With the supervisor running, **Save & push to BACnet** writes `schedules.json` and calls diy **`server_update_schedule`** (Monday→Sunday mapping is handled server-side).
