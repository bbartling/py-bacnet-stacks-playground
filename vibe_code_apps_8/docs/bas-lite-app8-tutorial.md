# BAS Lite on VOLTTRON — App 8 tutorial (human + AI)

This document is the **upgraded, self-contained** App 8 handoff: same **edge BACnet** story as App 7, but the UI is the **compiled React** app under `/app8/`, the web agent adds **operator APIs** (Pi metrics, `vctl`, driver config store, weekly occupancy schedule), and **§8** carries the full **systemd + logging + SD card** operations that used to live only in the App 7 bosspi tutorial—so **App 8 = enhanced stack + enhanced tutorial** in one place.

---

## Quick context (for AI assistants)

| Item | Typical value |
|------|----------------|
| Agent VIP | `ben.app8.web` |
| Install tag | `ben-app8-web` |
| HTTP prefix | `/app8` |
| UI (direct VOLTTRON) | `http://<pi>:8080/app8/index.html` |
| UI (via Caddy, optional) | `http://<pi>/` → redirects into `/app8/` |
| VOLTTRON root (Pi) | `/home/ben/volttron` |
| `VOLTTRON_HOME` | `/home/ben/.volttron` |
| Agent path on Pi | `/home/ben/volttron/volttron_data/ben_bacnet/app8_web_agent` |
| BACnet bench devices | `BensFakeAHU`, `Zone1VAV` (override via agent `config` → `bacnet_devices`) |
| OAT share agent (optional) | `ben.oat.share` / tag `ben-oat-share` — 15 min read + writes (see §4) |

---

## 1. Relationship to App 7

- **Same class of integration**: BACnet proxy + Platform Driver topics → web agent → browser.
- **App 7** served a small static/vanilla bundle under `/app7`.
- **App 8** serves a **production React build** from `app8_web_agent/webroot/` with richer pages: driver config tree, `vctl` table, occupancy editor, trends, faults.

### 1.1 App 8 is an **enhanced upgrade** — not a 1:1 folder copy

**`vibe_code_apps_8` does not duplicate every file from `vibe_code_apps_7`.** It **inherits the same bench idea** (BACnet, Platform Driver, Pi edge) and **replaces / extends** the pieces that needed to level up:

| Topic | App 7 folder | App 8 folder |
|-------|----------------|----------------|
| Operator web | `app7_web_agent` + hand-written `webroot/app7/*` | **`app8_web_agent`** + **Vite/React** `frontend/` → built **`webroot/`** |
| REST / UX surface | App 7 API (health, points, trends, …) | **Same BACnet semantics**, plus **Pi metrics**, **`vctl`**, **driver config store**, **occupancy schedule** APIs |
| Supervisory patterns | (none in repo) | **`oat_share_agent`** (e.g. OAT read / share on 15 min cadence) |
| Port 80 / TLS / Basic Auth | Discussed in passing | **`caddy/`** pack + **§7** below |
| Edge ops bible | **`bosspi-volttron-dataflow-and-storage-tutorial.md`** (deep) | **This document §8** now inlines the **systemd + SD + logging** material so App 8 is **self-contained**; App 7’s doc stays the reference for **App 7-only** paths and history |

So: **conceptually** App 8 is “App 7 + React + operator tooling + Caddy + OAT share”; **physically** it is a **sibling project** with **new and rewritten** trees, not a tarball copy of `vibe_code_apps_7`.

---

## 2. Preview the React UI before building static files

On a dev machine (PowerShell):

```powershell
cd vibe_code_apps_8\frontend
npm install
$env:VITE_DEV_PROXY_TARGET="http://192.168.204.12:8080"
npm run dev
```

Open **`http://localhost:5173/app8/`** (note the **`/app8/`** path — it matches the Vite `base`). The dev server proxies `/app8/api/*` to the Pi so you see live BACnet data. When satisfied, run **`npm run build`** to emit static files into the agent `webroot/`.

---

## 3. Build and deploy

On the dev machine:

```powershell
cd vibe_code_apps_8\frontend
npm install
npm run build
```

Deploy to the Pi (Windows example):

```powershell
cd vibe_code_apps_8
.\deploy-app8-to-bosspi.ps1
```

On the Pi, confirm:

```bash
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate
vctl status
```

---

## 4. Agent configuration (`app8_web_agent/config`)

Important keys:

| Key | Purpose |
|-----|---------|
| `route_prefix` | Default `/app8` — must match Vite `base`. |
| `bacnet_devices` | Driver topic names for `devices/<name>/all` subscriptions. |
| `volttron_root` | Working directory for `vctl` subprocess calls. |
| `vctl_path` | Full path to `vctl` in the venv. |
| `allow_agent_lifecycle` | When true, UI may call `vctl` start/stop/restart/remove (dangerous if exposed broadly). |
| `allow_driver_config_writes` | When true, UI may `vctl config store/delete` for `platform.driver`. |
| `site_model_path` | Optional JSON file (path relative to the agent package or absolute) defining `devices`, `points`, and optional `alarm_definitions` so a new site does not require editing Python. |
| `devices` / `points` / `alarm_definitions` | Optional inline keys in the same config file (same schema as the JSON file); values override the file when both are present. |
| `default_trend_point_id` | Which `pointId` the trends API and UI use first (otherwise the first point id in sorted order). |

See **`docs/replicate-any-building-lan-topology.md`** for OT LAN / BACnet / driver alignment and a deployment checklist. Example payload: `volttron_data/ben_bacnet/app8_web_agent/site_model.example.json`.

After editing **device** or **registry** configs in the UI, restart **`platform.driver`** from the System page (or `vctl restart --tag platform_driver`).

### Supervisory OAT share agent (`oat_share_agent`)

Many BAS jobs treat **outside air temperature** as **one physical sensor** (e.g. at a boiler or utility panel) that is **read once** and **written / shared** to other controllers (AHUs, VAVs) on an interval—often **15 minutes** for slow-changing air temperature.

This repo includes **`volttron_data/ben_bacnet/oat_share_agent/`**:

| Item | Value |
|------|--------|
| VIP identity | `ben.oat.share` |
| Install tag | `ben-oat-share` |
| Default interval | **900 s** (15 min), configurable `interval_seconds` |
| First run delay | **30 s** after start (`first_sync_delay_seconds`) so Platform Driver is warm |

**Behavior each cycle**

1. **`get_point`** on the **source** (`source_device_path`, `source_point`) — path must match the Platform Driver config-store key **without** the `devices/` prefix (e.g. store key `devices/campus/bench/ahu` → path `campus/bench/ahu`; many benches use a single segment like `BensFakeAHU`).
2. **`set_point`** on every **target** (`targets[].device_id`, `targets[].point_name`) — same `device_id` style as the App 8 setpoint API (driver topic name, e.g. `Zone1VAV`).

**Config (`oat_share_agent/config`)** ships with **`targets`: []** so a fresh install only **reads** and logs until you add consumer points. Each target point must exist in that device’s **registry CSV** and be **writable** if the BACnet object is not intrinsically writeable.

Example target (only after you add `SharedOAT` to the consumer registry):

```json
"targets": [
  {"device_id": "Zone1VAV", "point_name": "SharedOAT"}
]
```

Deploy from Windows (same pattern as App 8):

```powershell
cd vibe_code_apps_8
.\deploy-oat-share-to-bosspi.ps1
```

Manual install on the Pi:

```bash
vctl install --vip-identity ben.oat.share --tag ben-oat-share \
  /home/ben/volttron/volttron_data/ben_bacnet/oat_share_agent \
  --config /home/ben/volttron/volttron_data/ben_bacnet/oat_share_agent/config
vctl start --tag ben-oat-share
```

---

## 5. REST surface (selected)

| Method | Path | Notes |
|--------|------|--------|
| GET | `/app8/api/health` | Same shape as App 7 health, plus `defaultTrendPointId` for the trends UI/API default curve. |
| GET | `/app8/api/points` | Live point table + metadata. |
| POST | `/app8/api/setpoints/write` | BACnet write via Platform Driver RPC. |
| GET | `/app8/api/system/metrics` | Pi load, memory, root disk; optional `psutil` CPU %. |
| GET | `/app8/api/agents/vctl` | Raw `vctl list` plus parsed UUID rows. |
| POST | `/app8/api/agents/lifecycle` | JSON `{ "action": "start|stop|restart|remove", "tag"?: "...", "uuid"?: "..." }`. |
| GET | `/app8/api/driver/configs` | `vctl config list platform.driver`. |
| GET | `/app8/api/driver/config?name=...` | `vctl config get platform.driver <name>`. |
| POST | `/app8/api/driver/config/store` | JSON `{ "name", "content", "csv": bool }`. |
| POST | `/app8/api/driver/config/delete` | JSON `{ "name" }`. |
| GET/POST | `/app8/api/schedule` | Weekly occupancy JSON (agent-local `schedule_store.json`). |

---

## 6. BACnet + Platform Driver cheat sheet (edge)

Assumptions: `~/volttron` clone, `source env/bin/activate`, Python **3.10+** for current VOLTTRON 9.x / modular stacks (pin with `pip show volttron` on the Pi).

### BACnet utilities

```bash
cd ~/volttron && source env/bin/activate
cd scripts/bacnet
```

Edit `BACpypes.ini`: **`address` must be the edge NIC**, not the remote BACnet device.

### Scan

```bash
python bacnet_scan.py --range 0 4194303 --timeout 15 --csv-out devices.csv
```

### Bulk scrape configs

```bash
python grab_multiple_configs.py devices.csv --out-directory ./scan_output --ini ./BACpypes.ini
```

Produces `devices/` and `registry_configs/` suitable for `vctl config store`.

### Platform Driver config store (patterns)

```bash
vctl config store platform.driver registry_configs/ahu1.csv configs/ahu1.csv --csv
vctl config store platform.driver devices/site/building/ahu1 configs/ahu1.config
vctl config list platform.driver
```

Restart driver after changes:

```bash
vctl restart --tag platform_driver
```

### Proxy vs standalone scripts

Standalone `bacnet_scan.py` / `grab_bacnet_config.py` **conflict** with a running BACnet proxy unless you use the **proxy_*** variants. For normal runtime polling, use **BACnet Proxy + Platform Driver**.

### Weak devices

Set `"use_read_multiple": false` and tune `"max_per_request"` in BACnet driver config when devices reject RPM or segment poorly.

---

## 7. Caddy on port 80 — pretty URL, Basic Auth, optional TLS

VOLTTRON’s platform web is usually **`http://<pi>:8080/`** with a generic **`/index.html`** and each web agent on its own prefix (**`/app8/`**, **`/app7/`**, …). Operators often prefer **`http://<pi>/`** on **port 80** and (optionally) **HTTPS** with a login gate **outside** Python.

This repo ships a **separate systemd unit** `caddy-bas-lite` (not the stock Debian `caddy.service`) so you can opt in without silently hijacking a pre-existing Caddy install until you disable the default unit.

### What the config does

1. **Exact root redirect** — `GET /` → **`302`** to `{CADDY_APP_PREFIX}/index.html` (default **`/app8/index.html`**). That sends humans straight into the React shell instead of VOLTTRON’s default landing page.
2. **Reverse proxy** — everything else is **`reverse_proxy`** to **`127.0.0.1:8080`**, so `/app8/assets/...`, `/app8/api/health`, etc. are served by VOLTTRON unchanged. Caddy adds **`X-Forwarded-Proto`**, **`X-Forwarded-For`**, and **`X-Forwarded-Host`** so relative URLs and APIs behave correctly through the proxy.
3. **Optional Basic Auth** — when **`CADDY_BASIC_AUTH_ENABLE=1`**, Caddy’s **`basic_auth`** runs before the redirect/proxy. The password is a **bcrypt** hash from the Caddy CLI (never store plaintext on disk).
4. **Optional TLS** — when **`CADDY_TLS_ENABLE=1`**, **port 80** only issues a **permanent redirect to HTTPS**, and **port 443** terminates TLS using **`CADDY_TLS_CERT`** / **`CADDY_TLS_KEY`** (typically **self-signed** for bench LANs).

Packaged files live under **`vibe_code_apps_8/caddy/`** — see **`caddy/README.md`** for a file table.

### Install on the Pi (summary)

```bash
sudo bash vibe_code_apps_8/caddy/scripts/install-caddy-bas-lite.sh
sudo nano /etc/default/caddy-bas-lite
sudo bas-lite-render-caddyfile.sh
sudo caddy validate --config /etc/caddy/bas-lite.caddy --adapter caddyfile
sudo systemctl enable --now caddy-bas-lite
```

Boot-time behavior is controlled entirely by **`/etc/default/caddy-bas-lite`** (copied from **`caddy/env.example`**). The **`ExecStartPre`** in **`caddy-bas-lite.service`** re-renders the Caddyfile on every start so you can bake the same image and only change the env file per site.

### Set Basic Auth at boot

1. On the Pi (or any machine with the `caddy` binary):

   ```bash
   caddy hash-password --plaintext 'YourLongRandomPassword'
   ```

2. In **`/etc/default/caddy-bas-lite`**:

   - `CADDY_BASIC_AUTH_ENABLE=1`
   - `CADDY_BASIC_AUTH_USER=operator` (or any username)
   - `CADDY_BASIC_AUTH_HASH='<paste bcrypt line>'`

3. `sudo bas-lite-render-caddyfile.sh && sudo systemctl reload caddy-bas-lite`

### Point at App 7 instead of App 8

Set **`CADDY_APP_PREFIX=/app7`** to send `/` to **`/app7/index.html`**. No change to VOLTTRON is required beyond having that agent installed.

### Self-signed HTTPS

```bash
sudo bash vibe_code_apps_8/caddy/scripts/gen-selfsigned-cert.sh '192.168.204.12'
```

Then enable **`CADDY_TLS_ENABLE=1`** and ensure **`CADDY_TLS_CERT`** / **`CADDY_TLS_KEY`** match the generated paths. Browsers will show a warning until you trust the cert (bench-appropriate).

### Firewall

If **`ufw`** is enabled:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

---

## 8. Pi operations: Python, storage, logging, SD card, and systemd

This section is the **operational upgrade** bundled with App 8: the same **edge discipline** as the App 7 bosspi tutorial, **inlined here** so you do not have to cross-reference for **systemd**, **journald / RAM logging**, or **SD wear**. The canonical long-form narrative for the bench remains `vibe_code_apps_7/docs/bosspi-volttron-dataflow-and-storage-tutorial.md`.

### 8.1 Python version vs VOLTTRON

Match Python to the **exact** stack on the Pi:

- **Modular / PyPI `volttron`:** **Python ≥ 3.10** (tested baseline **3.10**; **3.11** often works — confirm with `pip show volttron`).
- **Older monolithic clones (e.g. 8.x):** follow that release’s install guide; do not assume 3.10+.

```bash
cd /home/ben/volttron
source env/bin/activate
python3 --version
pip show volttron | sed -n '1,12p'
```

### 8.2 Local storage posture (Pi)

- **Live BACnet / UI telemetry:** **memory-first and bounded** (same idea as App 7).
- **`VOLTTRON_HOME` (`~/.volttron`):** still holds configs, keystores, agent installs, and **some** logs — “RAM only” is **not** literal for the whole platform; avoid **high-churn** append logs on the SD card.

### 8.3 Logging and SD card wear

Logs may land in: **VOLTTRON files** under `~/volttron` or `~/.volttron`, **journald** (`volttron.service`), or **custom** agent files.

**Design goals**

- No **unbounded** per-sample or debug logging to the card in normal operation.  
- **INFO/WARN** by default; **DEBUG** only while troubleshooting.  
- **Rotate** or bound any file sink you keep on disk.

**Prefer journald in RAM (strong Pi pattern)** — logs lost on reboot; good for bench SD longevity:

```bash
sudo mkdir -p /etc/systemd/journald.conf.d
sudo tee /etc/systemd/journald.conf.d/volatile-storage.conf >/dev/null <<'EOF'
[Journal]
Storage=volatile
RuntimeMaxUse=64M
EOF
sudo systemctl restart systemd-journald
```

**If journald stays persistent**, cap it:

```ini
[Journal]
SystemMaxUse=100M
MaxRetentionSec=1week
```

```bash
journalctl --disk-usage
```

**VOLTTRON `volttron.log`:** avoid a single ever-growing file on the card — use **rotation**, **/run** (tmpfs) for the `-l` path (see **§8.5**), or stdout/stderr → journal only.

**Other SD practices:** tmpfs `/tmp`, sensible **swap/zram**, **noatime** where appropriate, move heavy DBs/historians to **USB SSD** or another host; **read-only root** is advanced.

**Inspect growth**

```bash
systemctl status volttron.service --no-pager
journalctl -u volttron.service -n 100 --no-pager
ls -lah /home/ben/.volttron
find /home/ben/.volttron -type f -printf '%s %p\n' 2>/dev/null | sort -nr | head -30
```

### 8.4 systemd: never mix service mode and manual debug

1. **Service mode** — `systemctl start volttron.service`; use `journalctl` / `systemctl status`.  
2. **Manual debug** — **`sudo systemctl stop volttron.service` first**, then activate the venv and run the platform manually.

Mixing the two causes **stale VIP sockets**, **double binds**, and confusing **`vctl status`**.

**Common commands**

```bash
sudo systemctl status volttron.service --no-pager
sudo systemctl stop volttron.service
sudo systemctl start volttron.service
sudo systemctl restart volttron.service
sudo systemctl enable volttron.service
journalctl -u volttron.service -n 100 --no-pager
```

### 8.5 Example `volttron.service` (journal + `/run` log, SD-friendly)

Adapt `User` / `Group` / paths. **`RuntimeDirectory=volttron`** + **`-l /run/volttron/volttron.log`** keeps the optional file log on **tmpfs** (cleared on reboot), not grinding the SD. **`StandardOutput`/`StandardError`** go to the journal.

```ini
[Unit]
Description=VOLTTRON platform (bosspi)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ben
Group=ben
RuntimeDirectory=volttron
WorkingDirectory=/home/ben/volttron
Environment=VOLTTRON_HOME=/home/ben/.volttron
ExecStart=/home/ben/volttron/env/bin/volttron -vv -l /run/volttron/volttron.log
Restart=on-failure
RestartSec=5

LimitNOFILE=65535

StandardOutput=journal
StandardError=journal
SyslogIdentifier=volttron

[Install]
WantedBy=multi-user.target
```

Install: `sudo cp volttron.service /etc/systemd/system/`, then `sudo systemctl daemon-reload` and `sudo systemctl enable --now volttron.service`.

### 8.6 BACnet bring-up ladder (App 8)

1. Pi platform healthy (**systemd** + `vctl status`)  
2. BACnet proxy healthy  
3. Platform Driver healthy and topics publishing  
4. **`/app8/api/health`** and live points look sane  
5. React UI renders (direct **:8080** or via **Caddy §7**)  

---

## 9. OpenClaw

Treat this folder plus this tutorial as **model context** for redeploy: build React → sync `app8_web_agent` → restart `ben-app8-web` → verify `/app8/api/health` and BACnet topics.
