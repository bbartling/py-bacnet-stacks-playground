# bosspi VOLTTRON + BACnet + App 7 tutorial

Practical handoff for humans and AI assistants: how the Raspberry Pi bench is wired, how BACnet data reaches the App 7 web UI, what lives on disk versus memory, how to run VOLTTRON under **systemd** safely, and how to avoid **SD card wear** on a Pi.

**Scope:** standalone **edge** VOLTTRON on `bosspi` with App 7. This document intentionally does **not** cover VOLTTRON Central, ForwardHistorian, or Open-FDD—those are separate integration tracks.

---

## Quick context (for AI assistants)

Use this block as grounding when editing agents or ops runbooks.

| Item | Value |
|------|--------|
| Edge host | `bosspi` (`192.168.204.12`), user `ben` |
| VOLTTRON source / venv | `/home/ben/volttron`, activate `source env/bin/activate` |
| `VOLTTRON_HOME` | `/home/ben/.volttron` |
| systemd unit | `volttron.service` |
| App 7 URL | `http://192.168.204.12:8080/app7/index.html` |
| BACnet bench devices | `BensFakeAHU` @ `192.168.204.13`, `Zone1VAV` @ `192.168.204.14` |
| Data path (mental model) | BACnet → BACnet proxy → Platform Driver → topics → App 7 web agent → browser |
| Pi constraints | Prefer **memory-first** telemetry and **bounded** logs; avoid unbounded disk logging |

Canonical upstream docs: [VOLTTRON index](https://volttron.readthedocs.io/en/main/index.html), [web framework](https://volttron.readthedocs.io/en/main/agent-framework/web-framework.html).

---

## 1. Big picture

**One** primary system for this tutorial:

1. **bosspi (`192.168.204.12`)** — Raspberry Pi edge runtime: native VOLTTRON in `~/volttron`, BACnet to bench devices, App 7 web agent.

**Bench BACnet devices**

- `BensFakeAHU` → `192.168.204.13`
- `Zone1VAV` → `192.168.204.14`

**End-to-end flow**

**BACnet devices → BACnet proxy → Platform Driver on bosspi → topic bus → App 7 web agent → browser**

---

## 2. Core online docs

- Main index: <https://volttron.readthedocs.io/en/main/index.html>
- Web framework: <https://volttron.readthedocs.io/en/main/agent-framework/web-framework.html>

Typical hard parts on this bench:

1. Reliable BACnet/IP on the Pi  
2. Healthy VOLTTRON under **systemd** (no duplicate manual + service starts)  
3. App 7 served correctly through the platform web service  

---

## 3. Python version vs VOLTTRON

**Rule:** match Python to the **exact** VOLTTRON stack you installed on the Pi.

- **Modular VOLTTRON** (current PyPI `volttron` / Eclipse direction): **Python ≥ 3.10** (PyPI metadata is `>=3.10,<4`; upstream docs target **3.10** as the tested baseline). **3.11** is often fine—confirm with your installed package and tests on the Pi.
- **Older monolithic VOLTTRON** (e.g. 8.x clones): may require an older Python; do not assume 3.10+ without reading that release’s install guide.

**On the Pi, always verify:**

```bash
cd /home/ben/volttron
source env/bin/activate
python3 --version
pip show volttron | sed -n '1,12p'
```

If you upgrade Python, recreate the venv and reinstall VOLTTRON and agents.

---

## 4. bosspi setup at a glance

### Host and paths

- Hostname: `bosspi`
- SSH: `ben@192.168.204.12`
- VOLTTRON repo: `/home/ben/volttron`
- `VOLTTRON_HOME`: `/home/ben/.volttron`
- systemd: `volttron.service`

### Shell prelude (every VOLTTRON CLI session)

```bash
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate
```

### Agents commonly involved on the bench

- `platform.bacnet_proxy`
- `platform.driver`
- `listener.bacnet` (if used)
- Custom bench agents (e.g. GL36 family) as configured
- `ben.app7.web` — App 7 web agent

---

## 5. How BACnet data reaches the frontend

### Step A — BACnet proxy

Speaks BACnet/IP to devices: discovery, reads, writes; backs Platform Driver.

### Step B — Platform Driver

Maps devices/points to publishable topics, for example:

- `devices/BensFakeAHU/all`
- `devices/Zone1VAV/all`

### Step C — Consumers

Listener agents, logic agents, **App 7 web agent**, etc., subscribe or query through the platform.

### Step D — App 7 web agent

Serves UI and app routes via VOLTTRON’s web framework; the browser does **not** speak BACnet.

**Browser path:**  
**browser → VOLTTRON web service → App 7 web agent → runtime/topics → Platform Driver → BACnet proxy → devices**

### Step E — Why URLs look like VOLTTRON

Agents register routes and static files; the platform web service hosts them—no separate nginx/node stack required for App 7 on this bench.

---

## 6. Local storage posture on the Pi

### Live telemetry

Source of truth for **live** values is runtime: BACnet reads, driver publications, agent state—not a large App-specific SQL store.

### App 7

Posture: **memory-first / bounded** for high-churn dashboard and trend buffers; avoid always-growing local databases for UI telemetry.

### `VOLTTRON_HOME` on disk

Even when apps are memory-friendly, the platform keeps control data under `/home/ben/.volttron` (configs, keystores, agent installs, **some logs** depending on setup). So “everything in RAM” is not literal—**high-churn telemetry** should be RAM-first; **platform state** stays where VOLTTRON expects it.

---

## 7. Logging and SD card wear

### Reality check

Logs may appear in:

1. Files under `VOLTTRON_HOME` or the repo (e.g. `volttron.log`)  
2. **journald** via `volttron.service`  
3. Custom agent or script file logging  

### Design goals on SD card storage

- **No high-rate, unbounded append logging** to the card for telemetry or per-sample traces.  
- **INFO/WARN** in normal operation; **DEBUG** only while troubleshooting.  
- **Bounded** retention everywhere something is allowed to grow.

### Prefer logs in memory (journald), not endless files on the card

**systemd journal to RAM (strong Pi pattern):** persist logs only when you need post-reboot forensics. Example drop-in:

```bash
sudo mkdir -p /etc/systemd/journald.conf.d
sudo tee /etc/systemd/journald.conf.d/volatile-storage.conf >/dev/null <<'EOF'
[Journal]
Storage=volatile
RuntimeMaxUse=64M
EOF
sudo systemctl restart systemd-journald
```

Tradeoff: journal contents are lost on reboot. For long investigations, temporarily switch to persistent storage or copy logs off-device.

**Cap persistent journal** (if you keep `Storage=persistent`):

```ini
[Journal]
SystemMaxUse=100M
MaxRetentionSec=1week
```

Pair with routine checks:

```bash
journalctl --disk-usage
```

### VOLTTRON file logs

If `volttron.log` grows without rotation, fix it: logrotate, platform logging settings, or route platform stdout/stderr through systemd only (see service template below) and avoid duplicate huge file sinks.

### Other Pi practices that reduce SD wear

- **tmpfs** for `/tmp` (often default on Raspberry Pi OS).  
- **ZRAM** or careful **swap** policy—avoid thrashing swap on the card.  
- **noatime** mounts where appropriate.  
- Move heavy databases or historians to **USB SSD** or another host if you add them later.  
- **Read-only root** is an advanced option for fixed appliances; plan before enabling.

### Commands to inspect growth

```bash
systemctl status volttron.service --no-pager
journalctl -u volttron.service -n 100 --no-pager
ls -lah /home/ben/.volttron
find /home/ben/.volttron -type f -printf '%s %p\n' 2>/dev/null | sort -nr | head -30
```

---

## 8. systemd: good service posture

### Two modes—never mix casually

1. **Service mode** — `systemctl start volttron.service`; use `journalctl` / `systemctl status`.  
2. **Manual debug** — `sudo systemctl stop volttron.service` first, then activate the venv and start the platform manually.

Running both causes confusing failures (stale VIP sockets, double binds, odd `vctl status`).

### Common commands

```bash
sudo systemctl status volttron.service --no-pager
sudo systemctl stop volttron.service
sudo systemctl start volttron.service
sudo systemctl restart volttron.service
sudo systemctl enable volttron.service
journalctl -u volttron.service -n 100 --no-pager
```

### Example `volttron.service` unit

Adapt `User`, `Group`, and paths to your Pi. This pattern exports `VOLTTRON_HOME`, uses the venv’s `volttron` executable, sends **stdout/stderr to the journal**, and puts the optional **`-l` file log under `/run`** (RAM, cleared on reboot) so routine platform logging does not wear the SD card.

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

Notes:

- **`RuntimeDirectory=volttron`** creates `/run/volttron` for this service; the **`-l`** path keeps a traditional log file **in memory**, not on the card. For deep postmortems across reboots, temporarily log to a **rotated** path on disk or raise journal persistence—then revert.  
- Install with `sudo cp volttron.service /etc/systemd/system/`, then `sudo systemctl daemon-reload` and `sudo systemctl enable --now volttron.service`.  
- Version the real unit under the repo if you want deploys reproducible (optional).

---

## 9. BACnet bring-up ladder

Order matters:

1. Pi platform healthy (systemd + `vctl status`)  
2. BACnet proxy healthy  
3. Platform Driver healthy and topics publishing  
4. App 7 endpoints return data  
5. Frontend renders  

Skipping straight to the UI wastes time when the field bus is the real fault.

---

## 10. Commands worth keeping handy

### On bosspi

```bash
cd /home/ben/volttron
export VOLTTRON_HOME=/home/ben/.volttron
source env/bin/activate
vctl status
```

### Browser

- `http://192.168.204.12:8080/app7/index.html`

### Optional: port 80 “front door” with Caddy

If you want **`http://<pi>/`** to land on the web agent (instead of VOLTTRON’s default **`/index.html`** on **8080**), use the **Caddy** pack in **`vibe_code_apps_8/caddy/`**: reverse proxy to **`127.0.0.1:8080`**, redirect `/` → **`/app7/index.html`** or **`/app8/index.html`**, optional **Basic Auth** and **TLS**, driven by **`/etc/default/caddy-bas-lite`**. See **`vibe_code_apps_8/docs/bas-lite-app8-tutorial.md`** §7 and **`vibe_code_apps_8/caddy/README.md`**.

---

## 11. Next-round checklist (optional)

- Record `pip show volttron` and `python3 --version` in your ops notes.  
- Version the real `/etc/systemd/system/volttron.service` next to this repo if desired.  
- Document BACnet driver config files for the two bench devices.  
- Audit disk growth quarterly after any new agents or historians.

---

## 12. Bottom line

- **bosspi** is the edge runtime.  
- **BACnet proxy + Platform Driver** ingest device data.  
- **App 7** is a VOLTTRON-hosted web agent on top.  
- **High-churn data** stays **memory-first and bounded**; **logs** should default to **bounded or RAM-backed journal**, not silent SD death by megabytes per hour.  
- **systemd** owns production starts; stop it before manual debugging.  
- **Python 3.10+** for current modular stacks—confirm against the installed `volttron` package on the Pi.

That is the architecture story for this folder.
