# vibe_code_apps_14 — BACnet routing research lab

Hands-on experiments with **[BACpypes3](https://github.com/JoelBender/BACpypes3)** routing samples, two [mini-device-revisited](https://github.com/JoelBender/BACpypes3/blob/main/samples/mini-device-revisited.py) servers on one host, and notes toward a **DIY BACnet/IP ↔ MS/TP** router (Misty3 + bacnet-stack).

**Status:** Active research (2026-05-18). Lab verified on `192.168.204.18`.

## Quick start

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_14
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

export HOST_IP=$(hostname -I | awk '{print $1}')

# Two BACnet devices, one OS, different ports
chmod +x scripts/*.sh
./scripts/start_two_minis.sh
.venv/bin/python scripts/discover_minis_unicast.py --host "$HOST_IP"
./scripts/stop_lab.sh

# 60s lab + tcpdump capture (sudo for packet capture)
sudo ./scripts/run_timed_lab.sh minis
sudo ./scripts/run_timed_lab.sh router

# IPv4 router (interactive) — stop minis first
./scripts/start_ipv4_router.sh
```

**Remote PC:** while `run_timed_lab.sh minis` runs on the server, on your laptop:

```bash
pip install bacpypes3 ifaddr
python scripts/remote_read_minis.py --server <server-lan-ip>
```

See [scripts/README-remote-probe.md](scripts/README-remote-probe.md). Confirms **direct** reads, not BACnet routing.

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/TUTORIAL-bacnet-routing-research.md](docs/TUTORIAL-bacnet-routing-research.md) | Full tutorial: routing, Misty3, bacnet-stack, roadmap |
| [docs/LAB_RESULTS.md](docs/LAB_RESULTS.md) | Verified results on this host |

## Port map (default)

| Role | UDP port | BACnet network |
|------|----------|----------------|
| Router leg A | 47808 | 100 |
| Router leg B | 47809 | 200 |
| MiniA | 47809 | — (standalone device, not routed net 100) |
| MiniB | 47810 | — |

Minis use **47809/47810** so they do not collide with the router on **47808/47809**.

## Two-machine routing lab

Run the **router** on the Pi/server; run **MiniA on `47808` and MiniB on `47809`** on your PC (see tutorial § Lab C). That is how an outside client sees **one routed plant** instead of two isolated UDP ports.

## Related apps

| App | Topic |
|-----|--------|
| **11** | Agentic BAS / Codex build |
| **12** | Pi DS18B20 BACnet device + AWS IoT |
| **13** | DIY BACnet router (planned) |
| **14** | This folder — routing research |
