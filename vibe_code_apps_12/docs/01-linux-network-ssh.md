---
title: Linux, network & SSH
nav_order: 1
---

# Linux, network & SSH

Before BACnet or AWS, the **gateway computer** must sit on the **same network as your controllers** and accept **SSH** from your build machine.

## What you need

| Item | Why |
|------|-----|
| Raspberry Pi 4/5 or Linux PC | Runs BACnet discover/read and MQTT client |
| Ethernet (preferred) or Wi‑Fi | Stable link to BACnet VLAN |
| Static or reserved DHCP IP | Ansible and bookmarks do not break |
| SSH enabled | Ansible deploys without a keyboard on the Pi |

## Network layout (typical lab)

```text
[Your PC / bensserver] ----SSH----> [Gateway Pi 192.168.204.12]
                                        |
                                        | UDP BACnet/IP
                                        v
                               [BASRT-B router 192.168.204.200]
                                        |
                                        MS/TP
                                        v
                               [Field controller device 5007]
```

## Step-by-step

### 1. Put the gateway on the BACnet subnet

- Configure **IPv4 address**, **mask**, and **gateway** so the Pi can reach:
  - Your BACnet/IP router (if MS/TP is behind a router)
  - Any BACnet devices that speak IP directly
- Example lab subnet: `192.168.204.0/24`.

**Check:** From the Pi, `ping 192.168.204.200` (router) succeeds.

### 2. Enable SSH

On Raspberry Pi OS:

```bash
sudo systemctl enable ssh
sudo systemctl start ssh
```

Create a user (e.g. `ben`) with sudo for Ansible `become`.

### 3. Log in from your build machine

```bash
ssh ben@192.168.204.12
```

If you use passwords, install **`sshpass`** on the build machine for Ansible:

```bash
sudo apt install sshpass
```

### 4. Optional — passwordless SSH

```bash
ssh-copy-id ben@192.168.204.12
```

Then Ansible `./deploy.sh -v` runs without `-ask-pass`.

### 5. Firewall notes

- **Outbound HTTPS (443)** — required for **AWS IoT Core** MQTT.
- **UDP 47808** — default BACnet/IP (PiTemp / some tools).
- **UDP 47809** — Vibe12 read driver when dual-stack on boss Pi (avoids port clash).

## Inventory entry

In `ansible/inventory.yml`:

```yaml
bacnet_pi:
  ansible_host: 192.168.204.12
  ansible_user: ben
```

## Troubleshooting

| Symptom | What to check |
|---------|----------------|
| SSH timeout | Wrong IP, VLAN, or firewall |
| Permission denied | User name, key, or password |
| BACnet discover finds nothing | Pi not on same subnet as router; wrong `--address` bind |
| MQTT fails later | Outbound 443 blocked |

Next: [BACnet IoT gateway](02-bacnet-gateway.md).
