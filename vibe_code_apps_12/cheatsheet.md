# Acme vm-bbartling — manual commissioning cheat sheet (Newbie 101)

Do this yourself on **bensserver** and **vm-bbartling**. No AI required.

**Building:** `acme` / `vm-bbartling`  
**Repo:** `~/py-bacnet-stacks-playground/vibe_code_apps_12`

---

## 0. Picture in your head (three machines)

| Machine | Who uses it | IP you care about |
|---------|-------------|-------------------|
| **bensserver** | You SSH here to run Ansible | Your lab LAN, e.g. `192.168.204.18` |
| **vm-bbartling** | BACnet edge (discover + MQTT) | **Tailscale** `100.122.106.124` for SSH only |
| **OT BACnet LAN** | VAVs, RTU, router | **`10.200.200.185`** on VM NIC `ens192` — **not** Tailscale |

```text
  [bensserver] --SSH/Ansible--> [vm-bbartling Tailscale]
                                    |
                                    | BACnet NIC ens192
                                    v
                              [10.200.200.0/24 OT LAN]
                              RTU-01, MS/TP router, VAVs
```

**Rule:** Ansible and SSH use Tailscale. BACnet bind uses `10.200.200.185/24:47809`.

### What `./deploy.sh` does (yes — it copies to the remote box)

You run deploy **on bensserver**. Ansible SSHs to the VM and:

| Step | What happens on **vm-bbartling** |
|------|----------------------------------|
| Copy code | `edge_bacnet/`, `requirements.txt`, etc. → `~/vibe_code_apps_12/` |
| Python venv | Creates/updates `~/vibe_code_apps_12/.venv` and installs pip deps |
| IoT certs | Copies PEMs from bensserver → `~/vibe_code_apps_12/aws_iot_certs/` |
| systemd | Installs `vibe12-bacnet-discover`, `vibe12-bacnet-read`, optional commissioning agent |
| Optional CSV | If you already have `edge_backup/local/acme/vm-bbartling/points.csv` on bensserver, pushes it to the VM |

It does **not** run BACnet discover for you — that is a separate step on the VM (or via the commissioning web UI).

`--verify` only runs health checks over SSH — **no file copy**, no restart.

---

## 1. One-time setup on bensserver

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12

# Python venv for Ansible (once)
cd ..
python3 -m venv .ansible_venv
.ansible_venv/bin/pip install ansible-core

# Private inventory (never commit passwords)
cd ansible
cp inventory.example.yml inventory.yml
cp host_vars/acme_vm_bbartling.yml.example host_vars/acme_vm_bbartling.yml
```

Edit **`ansible/inventory.yml`** — add under `pi_bcn.hosts`:

```yaml
        acme_vm_bbartling:
          ansible_host: 100.122.106.124
          ansible_user: bbartling
```

Edit **`ansible/host_vars/acme_vm_bbartling.yml`** — minimum:

```yaml
site_id: acme
building_id: vm-bbartling
bacnet_instance_id: 3456791
bacnet_device_name: GatewayVmBbartling
bacnet_bind_address: "10.200.200.185/24"
bacnet_edge_bind_address: "10.200.200.185/24:47809"
aws_iot_certs_local_dir: "{{ playbook_dir }}/files/aws_iot/acme-vm-bbartling"
aws_iot_cert_filename: device.pem.crt
aws_iot_key_filename: private.key
bacnet_edge_client_id: vibe12-acme_vm_bbartling
```

**Before MS/TP discover works**, you must add (get real values from your integrator / drawings):

```yaml
bacnet_route_aware: true
bacnet_router_ip: "10.200.200.XXX"      # BACnet/IP address of MS/TP router
bacnet_mstp_net: 11                      # trunk 11 net number (trunk 12 may differ)
bacnet_discover_range_low: 8
bacnet_discover_range_high: 8
bacnet_discover_timeout: 20
```

IoT certs: create Thing + PEM under `ansible/files/aws_iot/acme-vm-bbartling/` (see `docs/04-aws-iot-core.md`). Folder is gitignored.

---

## 2. SSH to the VM (test login)

From bensserver:

```bash
ssh bbartling@100.122.106.124
```

Use the **bbartling** password (not user `ben`).  
If this fails, fix SSH before BACnet.

On the VM once logged in:

```bash
hostname          # expect vm-bbartling
ip -4 addr show ens192    # expect 10.200.200.185/24
ls ~/vibe_code_apps_12
exit
```

**Deploy (password SSH is the default)** — from `ansible/` on bensserver:

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12/ansible
./deploy.sh --limit acme_vm_bbartling -v
```

`deploy.sh` automatically adds **`--ask-pass --ask-become-pass`** (you will be prompted).

- **SSH password** = login for `bbartling@100.122.106.124` (not user `ben`).
- **BECOME password** = sudo on the VM (often the same as SSH).
- Needs `sshpass` on bensserver: `sudo apt install sshpass`
- Repo `ansible/ansible.cfg` sets `password_mechanism = sshpass` (Ansible 2.19+).

**After `ssh-copy-id`** (skip password prompts):

```bash
ssh-copy-id bbartling@100.122.106.124
./deploy.sh --limit acme_vm_bbartling --no-ask-pass -v
```

---

## 3. Gate: ping the rooftop AHU (OT NIC must work)

From **vm-bbartling** (SSH in):

```bash
ping -c 3 10.200.200.27
```

| Result | Meaning |
|--------|---------|
| Replies | OT NIC routing is probably OK — continue |
| 100% loss | **Stop.** Fix `ens192` IP, cable, VLAN, or firewall before BACnet |

Expected device: **RTU-01**, BACnet instance **1100** (you will discover it later).

---

## 4. Deploy / refresh the edge stack

Run on **bensserver** — copies/updates files on the VM at **`~/vibe_code_apps_12/`** (see §0).

| Command | Copies files? | Use when |
|---------|---------------|----------|
| `./deploy.sh --limit acme_vm_bbartling -v` | **Yes** | Normal deploy (prompts for SSH/sudo password by default) |
| `./deploy.sh --limit acme_vm_bbartling --no-ask-pass -v` | **Yes** | After `ssh-copy-id` — no password prompts |
| `./deploy.sh --limit acme_vm_bbartling --verify -v` | **No** | Quick check: dirs, units, bind address |
| `./fetch_commissioning.sh --limit acme_vm_bbartling -v` | **No** (pull **from** VM) | Backup `points.csv` (password prompts by default) |

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12/ansible
./deploy.sh --limit acme_vm_bbartling -v
```

Confirm copy on the VM (SSH in):

```bash
ls -la ~/vibe_code_apps_12/edge_bacnet/
ls ~/vibe_code_apps_12/.venv/bin/python
```

On VM after deploy:

```bash
ls ~/vibe_code_apps_12/aws_iot_certs/
systemctl cat vibe12-bacnet-discover | grep address
# should show 10.200.200.185/24:47809
```

Read driver is **off** until you commission `points.csv` and redeploy with `enable_bacnet_read_driver=true`.

---

## 5. Phase A — global Who-Is (read-only)

Goal: see **any** BACnet devices on the wire. **No writes.**

### Option A — SSH + manual command (always works)

SSH to VM:

```bash
cd ~/vibe_code_apps_12

# Pure BACnet/IP (no MS/TP router) — rare on this job:
.venv/bin/python -m edge_bacnet.discover 1 4194303 \
  -o points_discovered_global.csv \
  --site-id acme --building-id vm-bbartling \
  --name GatewayVmBbartling --instance 3456791 \
  --address 10.200.200.185/24:47809

# MS/TP through router (usual for VAV trunks):
.venv/bin/python -m edge_bacnet.discover 1 4194303 \
  -o points_discovered_global.csv \
  --site-id acme --building-id vm-bbartling \
  --name GatewayVmBbartling --instance 3456791 \
  --address 10.200.200.185/24:47809 \
  --route-aware --network 1 \
  --router-ip 10.200.200.XXX \
  --mstp-net 11 \
  --timeout 20
```

Then:

```bash
wc -l points_discovered_global.csv
head -20 points_discovered_global.csv
```

| Result | Next step |
|--------|-----------|
| CSV has rows | Note which **device_instance** numbers appear; compare to VAV list below |
| Empty / errors | See troubleshooting §12 |

### Option B — systemd one-shot (same as Ansible template)

```bash
sudo systemctl start vibe12-bacnet-discover
journalctl -u vibe12-bacnet-discover -n 80 --no-pager
ls -la ~/vibe_code_apps_12/points_discovered.csv
```

### Option C — commissioning web (optional, from bensserver)

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12/commissioning_web
./run_dashboard.sh --restart -d
# copy token → browser http://127.0.0.1:8766 or Tailscale IP :8766
# connect → /discover 1 4194303  (or leave range blank for defaults in host_vars)
```

---

## 6. Phase B — one JCI VAV at a time

**Do not enable all VAVs at once** until device **8** template is verified.

### Trunk 11 device list

`8, 9, 10, 11, 14, 15, 16, 19, 20, 21`

### Trunk 12 device list

`22, 24, 25, 27, 29, 30, 31, 34, 36, 37, 38, 39`

### Step B1 — set discover range to ONE instance

On bensserver, edit `ansible/host_vars/acme_vm_bbartling.yml`:

```yaml
bacnet_discover_range_low: 8
bacnet_discover_range_high: 8
bacnet_mstp_net: 11    # use trunk 12 net when doing trunk 12 devices
```

Redeploy:

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12/ansible
./deploy.sh --limit acme_vm_bbartling -v
```

### Step B2 — run discover for that instance

On VM:

```bash
sudo systemctl start vibe12-bacnet-discover
journalctl -u vibe12-bacnet-discover -n 50 --no-pager
```

Or copy `points_discovered.csv` off the VM and open in Excel / LibreOffice.

### Step B3 — check the 9-point template (device 8)

Each VAV should expose these BACnet objects (names matter):

| object_type | object_instance | object_name |
|-------------|-----------------|-------------|
| analog-input | 1019 | DA-T |
| analog-input | 1106 | ZN-T |
| analog-output | 2014 | HTG-O |
| analog-output | 2131 | DPR-O |
| analog-value | 1103 | ZN-SP |
| analog-value | 3515 | SA-F |
| analog-value | 3615 | CLG-O |
| analog-value | 3472 | EFFCLG-SP |
| analog-value | 3473 | EFFHTG-SP |

If all nine exist with matching names → template is good.  
If not → **stop** and document differences before cloning to other VAVs.

### Step B4 — build `points.csv`

1. Start from discovered rows for device 8 only.
2. Keep only the 9 points above.
3. Set columns:

| Column | Example for VAV 8 |
|--------|-------------------|
| site_id | acme |
| building_id | vm-bbartling |
| system_id | jci-vav-8 |
| enabled | 1 |
| poll_interval_s | 60 |
| brick_class | e.g. Zone_Air_Temperature_Sensor (see boss Pi CSV) |
| brick_tag | e.g. VAV8-ZN-T |
| point_id | auto: `8-analog-input-1106` |

Reference CSV shape: `edge_backup/demo/bens-office/points.csv`

On VM, save as:

```text
~/vibe_code_apps_12/points.csv
```

Or build on bensserver and push via Ansible (next deploy copies from `edge_backup/local/` if you use fetch script).

### Step B5 — repeat for each instance

For each next device: change `bacnet_discover_range_low/high`, fix `bacnet_mstp_net` if trunk changes, redeploy, discover, append 9 rows to `points.csv`.

---

## 7. Backup CSV to bensserver (gitignored)

From bensserver:

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12/ansible
./fetch_commissioning.sh --limit acme_vm_bbartling -v
```

File lands in:

```text
edge_backup/local/acme/vm-bbartling/points.csv
```

Do **not** commit this to GitHub (real device names).

---

## 8. Phase C — turn on MQTT read driver

When `points.csv` is ready on the VM:

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12/ansible
./deploy.sh --limit acme_vm_bbartling -e enable_bacnet_read_driver=true -v
```

On VM:

```bash
sudo systemctl status vibe12-bacnet-read
journalctl -u vibe12-bacnet-read -f
```

Look for: `published N samples` every 60s, **no** `NOT_AUTHORIZED`.

MQTT topic pattern:

```text
vibe12/acme/vm-bbartling/{system_id}/{point_id}/telemetry
```

Example:

```text
vibe12/acme/vm-bbartling/jci-vav-8/8-analog-input-1106/telemetry
```

AWS IoT Console → MQTT test client → subscribe: `vibe12/acme/vm-bbartling/#`

---

## 9. Cloud check (bensserver)

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12
export WEB_PASSWORD='your-dashboard-password'
./scripts/validate_cloud_pipeline.sh
```

Or open the cloud dashboard URL from `aws_cloud_pipeline/DEPLOYED.md` and look for points under **acme / vm-bbartling**.

Cloud stack uses **90-day** telemetry TTL if you deployed with `TtlDays=90` in `sam-params.local.toml`.

---

## 10. Quick command reference

| Goal | Where | Command |
|------|-------|---------|
| SSH VM | bensserver | `ssh bbartling@100.122.106.124` |
| Deploy edge (copy to VM) | bensserver | `cd ansible && ./deploy.sh --limit acme_vm_bbartling -v` |
| Verify only (no copy) | bensserver | `./deploy.sh --limit acme_vm_bbartling --verify -v` |
| Ping RTU | VM | `ping 10.200.200.27` |
| Discover (manual) | VM | `python -m edge_bacnet.discover ...` (§5) |
| Discover (systemd) | VM | `sudo systemctl start vibe12-bacnet-discover` |
| Enable polling | bensserver | `./deploy.sh --limit acme_vm_bbartling -e enable_bacnet_read_driver=true -v` |
| Pull CSV backup | bensserver | `./fetch_commissioning.sh --limit acme_vm_bbartling -v` |
| Commissioning UI | bensserver | `commissioning_web/run_dashboard.sh --restart -d` |
| UI status | browser | connect + `/status` |
| UI discover one VAV | browser | `/discover 8 8` |

---

## 11. File map (where things live)

| File | Machine | Purpose |
|------|---------|---------|
| `ansible/inventory.yml` | bensserver | Tailscale IP for SSH |
| `ansible/host_vars/acme_vm_bbartling.yml` | bensserver | BACnet bind, router, discover range |
| `ansible/files/aws_iot/acme-vm-bbartling/*.pem` | bensserver | MQTT certs (gitignored) |
| `~/vibe_code_apps_12/` on VM | vm-bbartling | App + venv + CSV |
| `points_discovered.csv` | VM | Raw discover output |
| `points.csv` | VM | Commissioned points (enabled=1) |
| `edge_backup/local/acme/vm-bbartling/points.csv` | bensserver | Backup copy |

---

## 12. Troubleshooting

### SSH: `Permission denied` as `ben`

Use **`bbartling@100.122.106.124`**, not `ben@`.

### Ansible fails SSH but manual `ssh bbartling@...` works

1. Use **`--ask-pass --ask-become-pass`** until keys are installed.
2. Confirm **`ansible/ansible.cfg`** has `[ssh_connection] password_mechanism = sshpass` (Ansible 2.19+ default breaks password deploy without this).
3. Install **`sshpass`**: `sudo apt install sshpass`
4. Clear stale sockets: `rm -rf ~/.ansible/cp/*`
5. Or use keys: `ssh-copy-id bbartling@100.122.106.124` then deploy without `--ask-pass`

### BACnet discover finds nothing

1. `ping 10.200.200.27` from VM — if fail, fix NIC first.
2. Confirm bind: `ip addr show ens192` → `10.200.200.185`.
3. Confirm router IP and MSTP net in `host_vars`.
4. Try wire capture from bensserver:
   ```bash
   ./deploy.sh --limit acme_vm_bbartling --pcap --pcap-seconds 120
   ```
5. Only one discover range instance at a time while learning the wire.

### MQTT `NOT_AUTHORIZED`

- Cert files on VM under `~/vibe_code_apps_12/aws_iot_certs/`
- Client ID must be `vibe12-acme_vm_bbartling`
- IoT policy must allow `vibe12/+/+/+/+/telemetry`

### Read driver not running

```bash
# on VM
systemctl is-enabled vibe12-bacnet-read
grep enable_bacnet_read_driver ansible/host_vars/acme_vm_bbartling.yml  # on bensserver — must redeploy true
```

### Commissioning web “login required”

Paste token from `./run_dashboard.sh -d` banner → **connect** in browser.

### Dashboard already running

```bash
./run_dashboard.sh --status
./run_dashboard.sh --restart -d    # one safe command: stop + start
```

---

## 13. Done checklist (print and tick off)

- [ ] SSH `bbartling@100.122.106.124` works
- [ ] `ping 10.200.200.27` (RTU-01) works from VM
- [ ] Ansible deploy succeeds
- [ ] Global discover CSV has device instances
- [ ] Router IP + MSTP net documented in `host_vars`
- [ ] Device **8** — all 9 template points found
- [ ] `points.csv` has device 8 enabled rows
- [ ] Devices 9–21 trunk 11 commissioned
- [ ] Devices trunk 12 list commissioned
- [ ] `enable_bacnet_read_driver=true` deployed
- [ ] `journalctl -u vibe12-bacnet-read` shows publishes
- [ ] MQTT or cloud shows `acme/vm-bbartling` points
- [ ] `fetch_commissioning.sh` backup saved under `edge_backup/local/`

---

## 14. Read these docs (in order)

1. `docs/bacnet-commissioning.md`
2. `ansible/README.md`
3. `ansible/PRIVATE-MULTI-SITE.md`
4. `docs/04-aws-iot-core.md` (MQTT / Thing)
5. `commissioning_web/README.md` (optional UI)
6. `commissioning_web/prompts/acme-vm-bbartling-mission.example.md` (AI mission template — not needed for manual work)

---

## 15. What you are **not** doing (safety)

- **No BACnet writes** during discover/commissioning (read-only).
- **No passwords** in git or in committed YAML.
- **No guessing** router IP or MSTP net — ask whoever commissioned the MS/TP trunks.

---

*Last updated for vm-bbartling Acme JCI VAV job. Replace `10.200.200.XXX` and MSTP net numbers with your site’s real values before Phase B.*
