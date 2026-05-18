# BACnet routing research tutorial (BACpypes3 → Misty3 → DIY MS/TP router)

**App:** `vibe_code_apps_14`  
**Goal:** Learn BACnet **network-layer routing**, run reproducible labs, and plan a future **BACnet/IP ↔ MS/TP** DIY router (USB RS-485).

Primary upstream references:

- [BACpypes3 samples](https://github.com/JoelBender/BACpypes3/tree/main/samples) — `ipv4-to-ipv4.py`, `router-json.py`, [mini-device-revisited.py](https://github.com/JoelBender/BACpypes3/blob/main/samples/mini-device-revisited.py)
- [BACpypes3 sandbox](https://github.com/JoelBender/BACpypes3/tree/main/sandbox)
- [Misty3](https://github.com/raghavan97/misty3) — BACpypes3 ↔ MS/TP via C **bacnet-stack** agent
- [bacnet-stack router-mstp](https://github.com/bacnet-stack/bacnet-stack/tree/master/apps/router-mstp) — working IP↔MS/TP router in C

---

## 1. Concepts (three layers)

| Layer | What you are learning |
|-------|------------------------|
| **BACnet/IP UDP port** | One app binds one `IP:port` (default `47808`). Two apps cannot share the same port. |
| **BACnet network number** | Logical net (e.g. 100, 200). A **router** connects two+ network numbers. |
| **Route-aware address** | `200:30@192.168.1.50` = device MAC 30 on network 200, reached via router at `192.168.1.50`. |

BACpypes3’s [ipv4-to-ipv4](https://github.com/JoelBender/BACpypes3/blob/main/samples/ipv4-to-ipv4.py) sample uses **one NIC, two UDP ports** to simulate two BACnet/IP networks — **no second Ethernet card required** for that lab.

---

## 2. Lab A — Two mini devices on one machine (verified)

Uses [mini-device-revisited.py](https://raw.githubusercontent.com/JoelBender/BACpypes3/main/samples/mini-device-revisited.py): four points (read-only + commandable AV/BV).

### Setup (once)

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_14
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Library: **pip** `bacpypes3` + `ifaddr`. Sample scripts live in this repo under `samples/` (copied from upstream; not in the PyPI wheel).

### Run

```bash
export HOST_IP=$(hostname -I | awk '{print $1}')
./scripts/start_two_minis.sh
./scripts/discover_minis_unicast.py --host "$HOST_IP"
./scripts/stop_lab.sh
```

Default ports: **MiniA `47809`**, **MiniB `47810`** (avoids clashing with a router on `47808`/`47809`).

### From another PC on the LAN

Point your client at **explicit unicast** targets:

- `HOST_IP:47809` → device instance **1001**
- `HOST_IP:47810` → device instance **1002**

YABE and similar tools often assume **UDP 47808** broadcast; non-standard ports need unicast / manual address entry.

---

## 3. Lab B — IPv4-to-IPv4 router (one machine)

JSON pattern (from upstream `ipv4-to-ipv4.json`):

| UDP port | BACnet network |
|----------|----------------|
| 47808 | 100 |
| 47809 | 200 |

### Run on lab server

```bash
export HOST_IP=$(hostname -I | awk '{print $1}')
./scripts/start_ipv4_router.sh
```

Interactive commands (in router shell):

| Command | Purpose |
|---------|---------|
| `nsap` | Network service access point + router cache |
| `iartn` | I-Am-Router-To-Network |
| `wirtn` | Who-Is-Router-To-Network |
| `whois` | Who-Is (when other devices exist) |

### Port collision (important)

**Do not** start minis on `47808`/`47809` while the router uses those ports on the **same IP**. See `docs/LAB_RESULTS.md`.

---

## 4. Lab C — Full routing lab (two machines) — recommended next step

This matches how BACnet routing is meant to feel from an outside client.

```text
┌─────────────────────────────┐     LAN      ┌──────────────────────────────┐
│  Lab server (Pi / Linux)    │◄────────────►│  Your workstation            │
│  ipv4-to-ipv4 router        │              │  MiniA  PC_IP:47808  (net 100) │
│  192.168.x.1:47808  net 100 │              │  MiniB  PC_IP:47809  (net 200) │
│  192.168.x.1:47809  net 200 │              └──────────────────────────────┘
└─────────────────────────────┘
```

**Terminal 1 (server):** `./scripts/start_ipv4_router.sh`  
**Terminal 2 (PC):** mini on `47808`, mini on `47809`  
**Terminal 3:** client with route-aware addressing, e.g. read device `1001` on network `100` via router `192.168.x.1`.

From the server router shell, `wirtn` / `nsap` should show activity once the remote minis answer.

---

## 5. What does *not* work on one OS

```text
Router  owns  HOST:47808  and  HOST:47809
MiniA   wants  HOST:47808   ← EADDRINUSE
MiniB   wants  HOST:47809   ← EADDRINUSE
```

For **all-in-one** routing *logic* without separate UDP sockets, study BACpypes3 **VLAN** samples (virtual networks inside one application) — different tool, same teaching goal.

---

## 6. Misty3 — MS/TP before USB hardware

[Misty3](https://github.com/raghavan97/misty3) swaps:

```python
from misty3.mstplib import MSTPApplication as Application
from misty3.mstplib import MSTPArgumentParser as SimpleArgumentParser
```

Architecture: **BACpypes3 app ↔ MSTP agent ↔ serial ↔ bacnet-stack MS/TP**.

### Virtual serial (no RS-485 yet)

```bash
# Terminal 1
socat PTY,link=/var/tmp/ptyp0,b38400 PTY,link=/var/tmp/ttyp0,b38400

# Terminal 2 — device on MS/TP MAC 30
python samples/mini-device-revisited.py \
  --interface=/var/tmp/ptyp0 --mstpaddress=30 --instance=999

# Terminal 3 — discover on other end
python samples/discover-objects.py \
  --interface=/var/tmp/ttyp0 --mstpaddress=25 \
  --address=0.0.0.0:47809 999
```

When the USB adapter arrives, replace `/var/tmp/ptyp0` with `/dev/ttyUSB0` and add your user to the `dialout` group.

**Misty3 is a bridge pattern**, not a finished BACnet/IP↔MS/TP router product.

---

## 7. Fastest real IP ↔ MS/TP router — bacnet-stack

For a **working bench router** before writing Python glue:

```bash
git clone https://github.com/bacnet-stack/bacnet-stack.git
cd bacnet-stack
make router-mstp
```

Typical Linux env (from upstream README):

```bash
export BACNET_IFACE=eth0
export BACNET_MSTP_IFACE=/dev/ttyUSB0
export BACNET_MSTP_BAUD=38400
export BACNET_MSTP_MAC=99
export BACNET_IP_PORT=47808
export BACNET_IP_NET=1
export BACNET_MSTP_NET=2
./apps/router-mstp/router-mstp
```

One **Ethernet/Wi‑Fi** NIC + one **USB RS‑485** adapter — **not** two Ethernet NICs.

---

## 8. Future “BACpypes3-owned” DIY router (research target)

Target shape:

```text
Application.from_json(router config)
├── NetworkPort 1: BACnet/IP  (BACpypes3 ipv4)
└── NetworkPort 2: MS/TP adapter (Misty3-style C agent on /dev/ttyUSB0)
```

Borrow:

| Piece | From |
|-------|------|
| Router JSON, NSAP, `wirtn` / `iartn` | BACpypes3 samples |
| MS/TP PDU bridge | Misty3 |
| Field-proven MS/TP timing | bacnet-stack `router-mstp` |

---

## 9. Suggested roadmap

| Phase | Action |
|-------|--------|
| **1** | Run `./scripts/start_two_minis.sh` + unicast discovery (this repo) |
| **2** | Run `./scripts/start_ipv4_router.sh`; explore `nsap`, `iartn`, `wirtn` |
| **3** | Repeat Lab C with a **second machine** on the LAN |
| **4** | Misty3 + `socat` virtual serial |
| **5** | USB RS-485 + Misty3 on `/dev/ttyUSB0` |
| **6** | bacnet-stack `router-mstp` on the bench |
| **7** | Prototype BACpypes3 IP + custom MS/TP network port |

---

## 10. Docker note

BACpypes3 container docs warn that **broadcast** is awkward in Docker; prefer **host networking** or **BBMD/foreign device** for containerized clients. Do routing labs **bare metal** first.

---

## 11. Timed lab + Wireshark capture

```bash
sudo ./scripts/run_timed_lab.sh minis
sudo ./scripts/run_timed_lab.sh router
```

Runs **60 seconds** (override with `LAB_SECONDS=120`), logs discovery probes every 10s, writes `captures/<timestamp>-<mode>-60s.pcap`. See [REMOTE_DISCOVERY.md](REMOTE_DISCOVERY.md) for probing from a **second PC** while the lab runs.

## 12. Files in this app

| Path | Role |
|------|------|
| `scripts/start_two_minis.sh` | MiniA/MiniB on `:47809`/`:47810` |
| `scripts/start_ipv4_router.sh` | Render JSON + `ipv4-to-ipv4.py` |
| `scripts/discover_minis_unicast.py` | Prove both devices respond |
| `config/ipv4-router.template.json` | Router nets 100/200 on `47808`/`47809` |
| `docs/LAB_RESULTS.md` | Verified outcomes on `192.168.204.18` |
