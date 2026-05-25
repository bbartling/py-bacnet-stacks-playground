---
title: BACnet wire capture
nav_order: 5
---

# BACnet wire capture (pcap)

Validate RPM polling and MS/TP routing with a short **tcpdump** after each deploy.

## Enable on deploy

```bash
cd vibe_code_apps_12/ansible
./deploy.sh --limit bacnet_pi -e enable_bacnet_read_driver=true --pcap
```

| Variable | Default |
|----------|---------|
| `deploy_pcap_seconds` | **300** (5 minutes) |
| `deploy_pcap_wait_seconds` | **30** |
| Output file | `~/vibe_code_apps_12/captures/bacnet.pcap` |

Boss Pi filter: UDP **47808** and **47809** (PiTemp + Vibe12Edge).

Ansible waits until `vibe12-bacnet-read` is **active**, then starts capture in the background. Each deploy **overwrites** the same filename.

## Pull pcap to your laptop

After capture finishes:

```bash
scp ben@192.168.204.12:~/vibe_code_apps_12/captures/bacnet.pcap .
wireshark bacnet.pcap
```

Wireshark display filter: `bacnet` or `udp.port == 47808`.

## Manual capture on edge

```bash
~/vibe_code_apps_12/scripts/bacnet_tcpdump_once.sh \
  ~/vibe_code_apps_12/captures/bacnet.pcap \
  "udp port 47808 or udp port 47809" \
  300
```

Same pattern as [vibe_code_apps_14/captures](../../vibe_code_apps_14/captures/README.md).
