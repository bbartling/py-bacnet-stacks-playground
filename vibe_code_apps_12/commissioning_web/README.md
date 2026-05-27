# Vibe12 commissioning web — dial-in dashboard + edge HTTP agent

Dirt-simple commissioning UI: **no SSH** to start BACnet discover. Runs discover as a **background Python job** on the edge via HTTP.

## Architecture

| Component | Where | Port | Role |
|-----------|-------|------|------|
| **Edge agent** | Each gateway VM/Pi | `8765` | `POST /api/jobs/discover`, CSV download |
| **Dashboard** | bensserver | `8766` | Web UI + proxy to edges + **Codex wake** button |

Stdlib Python only — no Flask/React.

## Quick start (bensserver)

SSH in, start in the background, copy the printed token, close SSH:

```bash
cd vibe_code_apps_12/commissioning_web
chmod +x run_dashboard.sh
./run_dashboard.sh -d
```

The script prints a **login token** and LAN URLs. Paste the token into the browser top bar.

| Command | Action |
|---------|--------|
| `./run_dashboard.sh -d` | Start background (survives SSH logout) — **refuses if already running** |
| `./run_dashboard.sh --restart -d` | Stop any instance on port 8766, then start fresh |
| `./run_dashboard.sh --status` | Show pid + token |
| `./run_dashboard.sh --stop` | Stop tracked pid **and** orphan listeners on 8766 |
| `./run_dashboard.sh --new-token -d` | New token + restart |

Token is stored in `commissioning_web/.session.token` (gitignored, mode 600) and reused until `--new-token`.

Override: `export VIBE12_COMMISSION_TOKEN='your-own'` before starting.

Open **`http://<bensserver-lan-ip>:8766`** from any machine on your LAN.

### LAN not working from Windows but `localhost:8766` works (Cursor port forward)?

Cursor forwards **bensserver’s localhost** over SSH — that does **not** prove LAN works.

On bensserver the app listens on `0.0.0.0:8766` and responds on `192.168.204.18` locally. If Windows cannot open `http://192.168.204.18:8766`:

1. **Same subnet?** On Windows: `ping 192.168.204.18` — must reply. Your PC needs an address like `192.168.204.x` on the same LAN as `enp3s0`.
2. **Firewall on bensserver** (most common after ping works):
   ```bash
   cd commissioning_web
   sudo ./open_lan_port.sh
   ```
3. **Wi‑Fi client isolation** — some APs block laptop ↔ server; try wired or disable isolation.
4. **Tailscale instead of LAN** (if Windows has Tailscale):
   `http://100.119.25.53:8766/` (use bensserver’s Tailscale IP from `./run_dashboard.sh -d` banner).

Keep using **Cursor port forward** if you only need access from the machine running Cursor — no firewall change required.

Chat commands:

| Command | Action |
|---------|--------|
| `/help` | Show commands |
| `/wake` | Codex agent (spinner while working) |
| `/discover 8 8` | BACnet discover on selected gateway |
| `/status` | Edge + CSV check (no IPs in UI) |

Gateway picker shows **gateway 1**, **gateway 2** — not hostnames.

## Deploy edge agent (Ansible)

Enabled by default in `group_vars/pi_bcn.yml` (`enable_commissioning_web: true`).

```bash
cd ansible
./deploy.sh --limit acme_vm_bbartling -v
```

On the gateway:

```bash
curl -s http://127.0.0.1:8765/api/health
systemctl status vibe12-commissioning-agent
```

Set the **same** token on edge + dashboard (private host_vars), or copy from `.session.token` after `./run_dashboard.sh -d`:

```yaml
commissioning_web_token: "paste-token-from-server-start"
```

Written to `~/vibe_code_apps_12/commissioning_agent.env` on the edge.

## Manual edge run (debug)

```bash
cd ~/vibe_code_apps_12
export VIBE12_APP_DIR=$PWD
export VIBE12_COMMISSION_PORT=8765
.venv/bin/python -m edge_bacnet.commissioning_agent
```

## API (edge)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/health` | Liveness |
| GET | `/api/status` | Bind, CSV files, recent jobs |
| POST | `/api/jobs/discover` | Body: `{"range_low":"8","range_high":"8"}` optional |
| GET | `/api/jobs/{id}` | Job log tail |
| GET | `/api/files/points_discovered.csv` | Raw CSV |

Header: `X-Commission-Token` when token configured.

## Files

| Path | Git |
|------|-----|
| `commissioning_web/gateways.local.json` | gitignored |
| `commissioning_web/jobs/` | gitignored |
| `ansible/host_vars/*.yml` token | gitignored |

## Security

- Bind `0.0.0.0` — use **Tailscale** or firewall; set `VIBE12_COMMISSION_TOKEN`
- Read-only BACnet from discover — no writes via this UI
- Do not expose port 8765/8766 on the public internet without auth
