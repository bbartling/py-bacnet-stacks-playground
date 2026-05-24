**Beginner tutorial:** [ANSIBLE-BEGINNER.md](ANSIBLE-BEGINNER.md)

Ansible pushes the Vibe12 edge stack to **Linux hosts over SSH** (IP + user in `inventory.yml`).  
**Default = BACnet building gateway** (discover → CSV → poll). **GPIO is opt-in** on the boss Pi only.

---

## Two edge roles

| Role | Host | GPIO | MQTT source | Ansible config |
|------|------|------|-------------|----------------|
| **Building gateway** (default) | Any Linux box on the building LAN | **No** | BACnet read driver → `vibe12/{site}/{building}/{system}/{point}/telemetry` | `host_vars/<name>.yml` with `site_id`, `building_id` — see [`gateway.example.yml`](host_vars/gateway.example.yml) |
| **Boss Pi test bench** | `192.168.204.12` only | **Yes** (DS18B20) | GPIO hierarchical topics under `demo/bens-office/…` | [`host_vars/bacnet_pi.yml`](host_vars/bacnet_pi.yml) |

Field gateways never get `enable_ds18b20_*`. The playbook **stops and disables** `bacnet-ds18b20` if it was left on a host.

---

## Inventory (IP + SSH)

Edit [`inventory.yml`](inventory.yml) — one stanza per edge device:

```yaml
tower_a_edge:
  ansible_host: 10.0.1.50    # building gateway IP
  ansible_user: ben
```

Full multi-host template: [`inventory.example.yml`](inventory.example.yml).

**Deploy one host:**

```bash
./deploy.sh --limit tower_a_edge --ask-pass --ask-become-pass -v
```

**Deploy boss Pi only:**

```bash
./deploy.sh --limit bacnet_pi --ask-pass --ask-become-pass -v
```

Password SSH until `ssh-copy-id` is done: always pass `--ask-pass --ask-become-pass`.

---

## AWS IoT cert (shared PEM on all edges)

**Yes — reuse the same `.cert.pem` + `.private.key` on every gateway** for lab and early production.

1. Once on your laptop/build server: `./prepare_aws_iot_certs.sh` → files land in `files/aws_iot/`
2. Ansible copies them to each host: `~/vibe_code_apps_12/aws_iot_certs/`
3. **Topics** separate buildings (`site_id` / `building_id` in **host_vars**)
4. **Each host needs a unique MQTT client ID** — default `vibe12-{{ inventory_hostname }}` in [`group_vars/pi_bcn.yml`](group_vars/pi_bcn.yml)

Update your IoT **policy** on that certificate to allow:

- `iot:Connect` for client IDs `vibe12-*` (and `vibe12-gpio-bacnet-pi` on the bench Pi)
- `iot:Publish` on `vibe12/*` (plus `sdk/test/python` only if still used)

Details: [`files/aws_iot/README.txt`](files/aws_iot/README.txt)

Later you can issue **one IoT Thing per building** — same playbook, different `aws_iot_cert_filename` in host_vars.

---

## Building gateway workflow (typical)

### 1. Add host + building vars

```bash
cp host_vars/gateway.example.yml host_vars/tower_a_edge.yml
# edit site_id, building_id, ansible_host in inventory.yml
```

### 2. Deploy BACnet stack (read driver installed but stopped)

```bash
./prepare_aws_iot_certs.sh   # once
./deploy.sh --limit tower_a_edge -v
```

Installs: `edge_bacnet/`, `vibe12-bacnet-discover.service`, `vibe12-bacnet-read.service` (stopped), AWS certs. **No GPIO.**

### 3. Discover BACnet devices

```bash
ssh ben@10.0.1.50 'sudo systemctl start vibe12-bacnet-discover'
ssh ben@10.0.1.50 'journalctl -u vibe12-bacnet-discover -n 40 --no-pager'
# Edit ~/vibe_code_apps_12/points.csv — enabled=1, system_id, brick_class, brick_tag
```

### 4. Enable polling

```bash
./deploy.sh --limit tower_a_edge -e enable_bacnet_read_driver=true -v
```

MQTT per commissioned point:

```text
vibe12/{site_id}/{building_id}/{system_id}/{point_id}/telemetry
```

See [BACNET_COMMISSIONING.md](../BACNET_COMMISSIONING.md).

---

## Boss Pi test bench (GPIO only host)

[`host_vars/bacnet_pi.yml`](host_vars/bacnet_pi.yml) already enables GPIO + `bens-office` MQTT topics.

```bash
./deploy.sh --limit bacnet_pi --ask-pass --ask-become-pass -v
```

Topics (60 s AWS publish):

```text
vibe12/demo/bens-office/office/digital-temp-degC/telemetry
vibe12/demo/bens-office/office/digital-temp-degF/telemetry
```

---

## Other commands

| Goal | Command |
|------|---------|
| Full deploy + verify | `./deploy.sh -v` |
| One host | `./deploy.sh --limit HOST -v` |
| Checks only | `./deploy.sh --verify -v` |
| Skip post-checks | `./deploy.sh --no-verify -v` |

---

## Verify on edge

**BACnet gateway:**

```bash
systemctl list-unit-files 'vibe12-bacnet-*'
ls ~/vibe_code_apps_12/aws_iot_certs/
systemctl is-active vibe12-bacnet-read   # after enable_bacnet_read_driver
```

**GPIO (bacnet_pi only):**

```bash
systemctl is-active bacnet-ds18b20
journalctl -u bacnet-ds18b20 -n 25 --no-pager
```
