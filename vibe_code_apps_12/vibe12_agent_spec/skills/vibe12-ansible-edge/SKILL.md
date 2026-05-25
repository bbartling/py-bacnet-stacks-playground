---
name: vibe12-ansible-edge
description: >-
  Use when deploying Vibe12 to Raspberry Pi or gateway via Ansible, vibe12-bacnet-read,
  points.csv, AWS IoT certs, GPIO DS18B20, or bacnet_pi host vars. Triggers on:
  ansible deploy, bacnet_pi, read driver, 192.168.204.12, points.csv, enable_bacnet_read_driver.
---

# Vibe12 Ansible edge deploy

## Lab host

- Inventory: `ansible/inventory.yml` → `bacnet_pi` @ `192.168.204.12`
- Vars: `ansible/host_vars/bacnet_pi.yml`
- CSV: `commissioning/demo/bens-office/points.csv`

## One-time certs (build machine)

```bash
cd vibe_code_apps_12/ansible
./prepare_aws_iot_certs.sh
```

## Deploy

```bash
cd vibe_code_apps_12/ansible
./deploy.sh --limit bacnet_pi
```

## Expected services

| Unit | Role |
|------|------|
| `vibe12-bacnet-read` | BACnet RPM + GPIO → MQTT (60 s) |
| `bacnet-ds18b20` | Local BACnet PiTemp — **no** `--aws-iot` |

## Verify

```bash
ssh ben@192.168.204.12 'systemctl is-active vibe12-bacnet-read; journalctl -u vibe12-bacnet-read -n 3 --no-pager'
```

Expect `published 6 samples` each minute.

## Human responsibilities

- SSH access
- Discover → edit `points.csv` → set `enabled=1`
- Confirm MS/TP router IP and device instance

## Docs

- `ansible/README.md`
- `docs/phase-0-bens-office-lab.md`
- `memory/commissioning/PHASE_NOTEPAD.md`
