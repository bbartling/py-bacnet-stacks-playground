---
title: BACnet IoT gateway
nav_order: 2
---

# BACnet IoT gateway

The **edge gateway** is a small Linux service set that discovers BACnet points, polls them on a schedule, and publishes JSON to **AWS IoT Core** over MQTT.

## Software stack (what runs on the Pi)

| Component | Role |
|-----------|------|
| **`edge_bacnet/`** | Python scripts: discover, read driver, MQTT publish |
| **BACpypes3** | BACnet/IP (and route-aware MS/TP via router) |
| **systemd units** | `vibe12-bacnet-discover`, `vibe12-bacnet-read` |
| **AWS IoT device SDK** | MQTT TLS to `*.iot.*.amazonaws.com` |
| **Ansible** | Copies code + certs; no `git clone` on the Pi |

## How data flows

```text
points.csv  -->  read driver (60 s)  -->  RPM read present-value
       |                                      |
       |                                      v
       +---------------------------->  MQTT publish
                                         vibe12/site/bld/sys/point/telemetry
```

Discover is **read-only** (Who-Is / I-Am, optional RPM for metadata). The read driver only polls rows with **`enabled=1`** in `points.csv`.

## Deployment (Ansible)

From `vibe_code_apps_12/ansible` on your build machine:

```bash
./prepare_aws_iot_certs.sh          # once: PEM + key into ansible/files/aws_iot/
./deploy.sh --limit bacnet_pi \
  -e enable_bacnet_read_driver=true \
  --ask-pass --ask-become-pass -v
```

Files land under `~/vibe_code_apps_12/` on the gateway:

```text
edge_bacnet/          # Python modules
edge_backup/          # points.csv per site/building (bensserver backup)
aws_iot_certs/        # device.pem, private.key, AmazonRootCA1.pem
scripts/              # e.g. bacnet_tcpdump_once.sh
```

## Libraries and Python environment

- Repo root **`requirements.txt`** — BACnet + MQTT dependencies (installed by Ansible on the Pi).
- Read driver invoked as: `python3 -m edge_bacnet.read_driver` (exact module path in systemd template).

## BACnet bind and MS/TP router

In **`host_vars/bacnet_pi.yml`** (example):

```yaml
site_id: demo
building_id: bens-office   # must match edge_backup/ and cloud dashboard picker
bacnet_edge_bind_address: "192.168.204.12/24:47809"
bacnet_route_aware: true
bacnet_router_ip: 192.168.204.200
bacnet_mstp_net: 2000
```

**Route-aware** mode sends Who-Is through the BACnet/IP router to MS/TP devices.

## Dual BACnet on boss Pi (lab)

| Service | UDP port | Purpose |
|---------|----------|---------|
| `bacnet-ds18b20` | 47808 | Local 1-wire demo |
| `vibe12-bacnet-read` | 47809 | Commissioned points + GPIO in same MQTT cycle |

Only **one MQTT client id** (`basicPubSub`) is used — GPIO samples ride with BACnet in the read driver when enabled.

## Verify after deploy

```bash
ssh ben@192.168.204.12 'systemctl is-active vibe12-bacnet-read'
ssh ben@192.168.204.12 'journalctl -u vibe12-bacnet-read -n 20 --no-pager'
```

Look for `published N samples` and no `NOT_AUTHORIZED` MQTT errors.

Next: [Commissioning & CSV cleaning](03-commissioning-csv.md).
