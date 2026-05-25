---
title: Edge deploy (Ansible)
nav_order: 2
---

# Edge deploy (Ansible)

Ansible pushes the Vibe12 stack from your **build machine** (bensserver) to edge hosts over **SSH**. The Pi does **not** need a git clone — only selected files are copied.

```text
bensserver: ~/py-bacnet-stacks-playground/
       │  ansible-playbook / deploy.sh
       ▼
edge Pi:  ~/vibe_code_apps_12/
```

Beginner walkthrough: [`ansible/ANSIBLE-BEGINNER.md`](../ansible/ANSIBLE-BEGINNER.md).

## Two edge roles

| Role | Example host | GPIO | MQTT |
|------|----------------|------|------|
| **Building gateway** | `tower_a_edge` | Off | BACnet read driver only |
| **Boss Pi test bench** | `bacnet_pi` @ `192.168.204.12` | DS18B20 + BACnet MS/TP | One `basicPubSub` client (GPIO + BACnet) |

## Quick start (boss Pi)

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12/ansible
./prepare_aws_iot_certs.sh    # once on bensserver
./deploy.sh --limit bacnet_pi -e enable_bacnet_read_driver=true --ask-pass --ask-become-pass -v
```

Optional 5-minute BACnet wire capture:

```bash
./deploy.sh --limit bacnet_pi -e enable_bacnet_read_driver=true --pcap --ask-pass --ask-become-pass -v
```

## Inventory

Edit [`ansible/inventory.yml`](../ansible/inventory.yml):

```yaml
bacnet_pi:
  ansible_host: 192.168.204.12
  ansible_user: ben
```

Per-building MQTT scope: [`ansible/host_vars/<host>.yml`](../ansible/host_vars/) — `site_id`, `building_id`.

## AWS IoT certificate (shared across edges)

1. Run `./prepare_aws_iot_certs.sh` → `ansible/files/aws_iot/`
2. Deploy copies PEM/key to `~/vibe_code_apps_12/aws_iot_certs/` on each host
3. IoT **policy** must allow publish to `vibe12/*` and connect as **`basicPubSub`** (current lab cert) or extend policy per [`aws_iot_core_test/policy-vibe12-multi-client.json`](../aws_iot_core_test/policy-vibe12-multi-client.json)

## Common commands

| Goal | Command |
|------|---------|
| Deploy one host | `./deploy.sh --limit HOST -v` |
| Enable BACnet polling | `-e enable_bacnet_read_driver=true` |
| Backup commissioned CSV | `./fetch_commissioning.sh --limit HOST -v` |
| Deploy + 5 min pcap | `--pcap` |
| Verify only | `./deploy.sh --verify` |

## Dual BACnet stacks (boss Pi)

- **PiTemp** — `bacnet-ds18b20.service`, UDP **47808**
- **Vibe12Edge** — `vibe12-bacnet-read.service`, UDP **47809**

Both can run together; MQTT publishes from the read driver only.

## Verify on edge

```bash
systemctl is-active vibe12-bacnet-read
journalctl -u vibe12-bacnet-read -n 20 --no-pager
```

MQTT test client (AWS console): `vibe12/demo/bens-office/#`
