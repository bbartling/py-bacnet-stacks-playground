---
name: vibe12-wire-pcap
description: >-
  Use when capturing or downloading BACnet wire pcaps from the Pi, tcpdump,
  fetch_bacnet_pcap, or validating MS/TP traffic. Triggers on: pcap, tcpdump,
  wireshark, fetch_bacnet_pcap, bacnet.pcap, wire capture.
---

# Vibe12 wire capture (easy button)

## One command (bensserver)

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12
./scripts/fetch_bacnet_pcap.sh              # 5 min capture + download
./scripts/fetch_bacnet_pcap.sh --pull-only  # download only
```

Output:

- `~/captures/bacnet.pcap`
- `~/bacnet-latest.pcap` (symlink)

Env: `PI_HOST=192.168.204.12` `PI_USER=ben`

## Ansible deploy capture

```bash
cd ansible
./deploy.sh --limit bacnet_pi --pcap
./deploy.sh --limit bacnet_pi --pcap --pcap-seconds 300
```

## Filter (boss Pi)

`udp port 47808 or udp port 47809` — PiTemp + Vibe12Edge

## Docs

- `docs/wire-capture.md`
- `captures/README.md`
