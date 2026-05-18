# Lab results (verified on this host)

**Date:** 2026-05-18  
**Host:** `192.168.204.18` (adjust for your LAN)  
**Deps:** pip `bacpypes3` + `ifaddr` in `.venv`; sample scripts in `samples/` (not a git clone of BACpypes3).

## Two mini devices, one OS, different UDP ports — **works**

| Process | Instance | Bind |
|---------|----------|------|
| MiniA | 1001 | `192.168.204.18:47809` |
| MiniB | 1002 | `192.168.204.18:47810` |

Both processes stayed up; `ss -ulnp` showed both UDP sockets.

Unicast Who-Is from client `:47812` returned:

```text
device,1001 @ 192.168.204.18:47809
device,1002 @ 192.168.204.18:47810
```

**Note:** Standard broadcast Who-Is to `:47808` does **not** find devices on `:47809`/`:47810`. Tools must target the correct **IP:port** or use route-aware addressing behind a router.

## Router + minis on overlapping ports — **fails (expected)**

`ipv4-to-ipv4` / `router-json` binds:

- `HOST:47808` → BACnet network **100**
- `HOST:47809` → BACnet network **200**

If MiniA also binds `HOST:47809`, the OS returns **`Address already in use`**. Only one process owns each UDP port.

## Router alone on this host — **works**

With minis stopped, rendered `config/ipv4-router.rendered.json` starts and holds `:47808` and `:47809`.

**Fix (2026-05-18):** `NotImplementedError: None` was a truncated JSON template — network-port objects must include `"bacnet-ip-mode": "normal"` (match upstream `ipv4-to-ipv4.json`). Use `./scripts/start_ipv4_router.sh` (interactive) or `router_daemon.py` inside `run_timed_lab.sh router`.

## Timed lab + tcpdump

```bash
sudo ./scripts/run_timed_lab.sh minis    # 60s, captures UDP to captures/*.pcap
sudo ./scripts/run_timed_lab.sh router
```

Set `LAB_SECONDS=120` to run longer. Pcaps are intended for commit under `captures/` (learning only).

## Recommended multi-machine routing lab

```text
Lab server (e.g. Pi 192.168.204.18)
└── BACpypes3 ipv4-to-ipv4 router
    ├── :47808  BACnet network 100
    └── :47809  BACnet network 200

Your PC (second machine)
├── MiniA  YOUR_PC_IP:47808   (lives on router network 100 port world)
└── MiniB  YOUR_PC_IP:47809   (lives on router network 200 port world)
```

From a third machine, route-aware reads look like `100:1001@192.168.204.18` (device on remote net 100 behind router at `.18`).

## Same-OS “looks like one app” — clarify

Two minis on `:47809` and `:47810` are **two separate BACnet/IP UDP islands**, not one routed fabric. To look like **one routed BACnet plant**, you need the **router process** plus devices on the router’s **network numbers/ports** (usually split across hosts as above).
