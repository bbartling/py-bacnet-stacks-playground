# Wake task — Acme vm-bbartling JCI VAV MS/TP discover + CSV poll

_Copy to `cron_codex/state/wake_task.md` or paste into Codex TUI `/mini`. No passwords in this file._

## Current focus (mini)

**Mission:** BACnet **read-only** discover and **points.csv** commissioning for **JCI VAV boxes** on vm-bbartling (Acme). Start with **one global Who-Is** on the bind, then **one device instance at a time** on MS/TP trunks 11 and 12. All VAVs share the same point program — commission the **9-point template** on every box.

### Where scripts live (bensserver repo)

| What | Path (from repo root `vibe_code_apps_12/`) |
|------|---------------------------------------------|
| Discover module | `edge_bacnet/discover.py` → run as `python -m edge_bacnet.discover` |
| Read driver | `edge_bacnet/read_driver.py` → `python -m edge_bacnet.read_driver` |
| Point ID helpers | `edge_bacnet/point_id.py`, `edge_bacnet/config.py` (CSV columns) |
| Ansible deploy | `ansible/deploy.sh`, `ansible/deploy.yml` |
| Discover systemd template | `ansible/templates/vibe12-bacnet-discover.service.j2` |
| Read driver systemd | `ansible/templates/vibe12-bacnet-read.service.j2` |
| Fetch CSV backup | `ansible/fetch_commissioning.sh` |
| Host vars example | `ansible/host_vars/acme_vm_bbartling.yml.example` |
| Boss Pi MS/TP reference | `ansible/host_vars/bacnet_pi.yml` (router pattern) |
| Commissioned CSV example | `commissioning/demo/bens-office/points.csv` |
| BACnet commissioning doc | `docs/bacnet-commissioning.md` |

**On the edge VM** (after Ansible deploy): app dir `~/vibe_code_apps_12/`, venv `~/vibe_code_apps_12/.venv/bin/python`, CSV outputs `points_discovered.csv` / `points.csv`.

### Gateway facts (already deployed)

- Inventory: **`acme_vm_bbartling`**
- SSH: Tailscale **`100.122.106.124`**, user **`bbartling`** (password via `--ask-pass` / env — never commit)
- BACnet bind: **`10.200.200.185/24:47809`** on **`ens192`** — NOT Tailscale
- `site_id` / `building_id`: **`acme` / `vm-bbartling`**
- IoT: Thing **`acme-vm-bbartling-gw`**, client **`vibe12-acme_vm_bbartling`**
- Read driver: **OFF** until `points.csv` is ready
- MQTT: `vibe12/acme/vm-bbartling/{system_id}/{point_id}/telemetry`

### MS/TP target inventory (JCI VAV — same program on each)

**Discover one device instance at a time** (narrow range in host_vars or CLI args). Human labels trunks for documentation; BACnet key is **device instance**.

| Trunk (label) | Device instances (Who-Is / discover range low=high) |
|---------------|------------------------------------------------------|
| MS/TP trunk 11 | **8, 9, 10, 11, 14, 15, 16, 19, 20, 21** |
| MS/TP trunk 12 | **22, 24, 25, 27, 29, 30, 31, 34, 36, 37, 38, 39** |

**Before trunk work:** confirm in gitignored `host_vars/acme_vm_bbartling.yml`:

```yaml
bacnet_route_aware: true
bacnet_router_ip: <HUMAN: BACnet/IP router IP on 10.200.200.x>
bacnet_mstp_net: <HUMAN: MSTP network number — trunk 11 vs 12 may differ>
bacnet_discover_range_low: <single instance for this pass>
bacnet_discover_range_high: <same as low for one-at-a-time>
bacnet_discover_timeout: 20
```

Redeploy after host_vars change: `cd ansible && ./deploy.sh --limit acme_vm_bbartling -v`

### JCI VAV point template (enable on EVERY commissioned device)

Same `object_type` + `object_instance` on each VAV. Use `system_id`: `jci-vav-{device_instance}` (e.g. `jci-vav-8`). `point_id` auto: `{device_instance}-{object_type}-{object_instance}`.

| object_type | object_instance | object_name | description | brick_class (suggested) |
|-------------|-----------------|-------------|-------------|-------------------------|
| analog-input | 1019 | DA-T | Discharge Air Temperature | Discharge_Air_Temperature_Sensor |
| analog-input | 1106 | ZN-T | Zone Temperature | Zone_Air_Temperature_Sensor |
| analog-output | 2014 | HTG-O | Heating Output | Heating_Command |
| analog-output | 2131 | DPR-O | Supply Air Damper Output | Damper_Position_Command |
| analog-value | 1103 | ZN-SP | Zone Setpoint | Zone_Air_Temperature_Setpoint |
| analog-value | 3515 | SA-F | Supply Air Flow | Supply_Air_Flow_Sensor |
| analog-value | 3615 | CLG-O | Cooling Output | Cooling_Command |
| analog-value | 3472 | EFFCLG-SP | Effective Cooling Setpoint | Effective_Cooling_Temperature_Setpoint |
| analog-value | 3473 | EFFHTG-SP | Effective Heating Setpoint | Effective_Heating_Temperature_Setpoint |

CSV rows: `enabled=1`, `poll_interval_s=60`, `site_id=acme`, `building_id=vm-bbartling`, `brick_tag` e.g. `VAV8-DA-T`.

## Do this in order

### Phase A — Global discover (whole wire, read-only)

1. `cd ansible && ./deploy.sh --limit acme_vm_bbartling --verify -v`
2. SSH vm: confirm `ens192` = `10.200.200.185`, certs in `~/vibe_code_apps_12/aws_iot_certs/`
3. **Broad Who-Is** (if router known, set route-aware host_vars first; else try pure IP range):

```bash
# On VM — match systemd or run manually:
cd ~/vibe_code_apps_12
.venv/bin/python -m edge_bacnet.discover 1 4194303 \
  -o points_discovered_global.csv \
  --site-id acme --building-id vm-bbartling \
  --name GatewayVmBbartling --instance 3456791 \
  --address 10.200.200.185/24:47809
# If MS/TP: add --route-aware --network 1 --router-ip <IP> --mstp-net <NET> --timeout 20
```

Or: `sudo systemctl start vibe12-bacnet-discover` (uses host_vars range) + `journalctl -u vibe12-bacnet-discover -n 80`

4. **If zero I-Ams:** `./deploy.sh --limit acme_vm_bbartling --pcap --pcap-seconds 120`; stop and document blocker (router IP, VLAN, trunk net numbers).

5. **If I-Ams found:** note which device instances respond; compare to trunk 11/12 list above.

### Phase B — One VAV at a time (start trunk 11)

For **first device instance 8 only**:

1. Set `bacnet_discover_range_low/high: 8`, correct `bacnet_mstp_net` for trunk 11, redeploy
2. Run discover → `points_discovered.csv`
3. **Verify template points exist** (1019, 1106, 2014, 2131, 1103, 3515, 3615, 3472, 3473) — match object names DA-T, ZN-T, etc.
4. If template matches: build **9 enabled rows** for device 8 in `points.csv` (do not enable whole object-list yet)
5. If template differs: document delta in `memory/integrations/bacnet.md` before bulk-commissioning other VAVs

Repeat for trunk 11 instances **9, 10, 11, 14, 15, 16, 19, 20, 21** — append to same `points.csv`.

Then trunk 12: **22, 24, 25, 27, 29, 30, 31, 34, 36, 37, 38, 39** (adjust `bacnet_mstp_net` if trunk 12 uses a different MS/TP net).

### Phase C — Enable poll + cloud

```bash
cd ansible
./fetch_commissioning.sh --limit acme_vm_bbartling -v   # → commissioning/local/acme/vm-bbartling/
./deploy.sh --limit acme_vm_bbartling -e enable_bacnet_read_driver=true -v
```

VM: `journalctl -u vibe12-bacnet-read -f` — expect `published N samples`, no NOT_AUTHORIZED.

Cloud: `WEB_PASSWORD` in env → `./scripts/validate_cloud_pipeline.sh` or `/api/points/acme/vm-bbartling`.

Update `memory/job/lab_facts.md` + `memory/integrations/bacnet.md` (no secrets).

## Guardrails

- **Read-only BACnet** — no writes
- No secrets/PEMs/passwords in git
- Do not commit `commissioning/local/` unless operator asks
- Stop if router IP or MSTP net for trunk 11/12 is unknown — ask human, do not guess
- Stop if device 8 template points missing — fix template before cloning to 21 other VAVs

## Done when

- [ ] Global discover CSV shows OT devices (or blocker documented)
- [ ] Device **8** template verified; 9 points enabled in `points.csv`
- [ ] All trunk 11 + trunk 12 VAV instances commissioned (or explicit skip list)
- [ ] `vibe12-bacnet-read` publishing MQTT for `vibe12/acme/vm-bbartling/jci-vav-*/…`
- [ ] Cloud ingest shows acme/vm-bbartling points
- [ ] `fetch_commissioning.sh` backup in `commissioning/local/acme/vm-bbartling/`

## Skill

`bacnet-point-modeling`, `field-commissioning-phases`, `vibe12-ansible-edge`

## Escalation

- Zero I-Ams after bind + pcap → human: router IP, trunk 11/12 MSTP net numbers, field panel online
- Template mismatch on device 8 → human: JCI program revision or non-standard instance map
