# Two BACpypes3 apps on one PC — **with BACnet routing**

Same ping-pong game as [../run_two_on_same_pc/README.md](../run_two_on_same_pc/README.md), but peers talk across **BACnet networks 100 and 200** through a **BACpypes3 IPv4 router** ([ipv4-to-ipv4](https://github.com/JoelBender/BACpypes3/blob/main/samples/ipv4-to-ipv4.py) style).

## Schematic

```text
  Same computer — two terminals

  Terminal 1                              Terminal 2
  ping_pong_router_and_player_a.py        ping_pong_player_b.py
  device 998  "pong" on net 100           device 1002 "pong" on net 200
  router UDP :47830 (net 100)  <--------> :47833
            \                            /
             \------ router :47831 ------/
                    (net 200 leg)
```

**Why one script combines router + player A:** each BACnet/IP app binds its own UDP port. Broadcast **Who-Is-Router-To-Network** does not cross ports on a single host, so a standalone router on `:47830` and a separate player A on `:47832` cannot discover each other. The working pattern is the **router process on net 100/200** plus **player B on net 200** in a second terminal.

## Before you start

1. `pip install bacpypes3 ifaddr`

2. Edit **`HOST_IP`** in both `.py` files if your PC is not `192.168.204.18`.

3. Use **`/24`** in player B’s bind (`HOST_IP/24:port`).

4. Do not run the flat ping-pong lab or campus BACnet on the same UDP ports at once.

## Run in two terminals (manual)

Start **terminal 1 first**, then **terminal 2**. Leave both running; **Ctrl+C** to stop.

### Linux

**Terminal 1 — router + player A (net 100, starter)**

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_14/run_two_on_same_pc_router
python3 ping_pong_router_and_player_a.py
```

**Terminal 2 — player B (net 200)**

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_14/run_two_on_same_pc_router
python3 ping_pong_player_b.py
```

### Windows (PowerShell or Command Prompt)

**Terminal 1**

```powershell
cd py-bacnet-stacks-playground\vibe_code_apps_14\run_two_on_same_pc_router
python ping_pong_router_and_player_a.py
```

**Terminal 2**

```powershell
cd py-bacnet-stacks-playground\vibe_code_apps_14\run_two_on_same_pc_router
python ping_pong_player_b.py
```

## What you should see

Alternating lines like:

```text
[A] HIT  peer=0  local 0 -> 1
[B] HIT  peer=1  local 0 -> 2
[A] HIT  peer=2  local 1 -> 3
...
```

Counters reset at **100**. Player B logs `router for net 100: …:47831` after unicast router discovery.

## Flat lab vs router lab

| | [run_two_on_same_pc](../run_two_on_same_pc/) | This folder |
|--|---------------------------------------------|-------------|
| Terminals | 2 | 2 |
| Reach peer | `IP:47810` direct | `200:IP:47833` / `100:IP:47830@IP:47831` |
| BACnet networks | local only | **100** and **200** |
| Field pattern | Trane-style **per-port** campus | **DNET / router** between segments |

## Ports (hard-coded)

| Role | Script | UDP | BACnet net |
|------|--------|-----|------------|
| Router + A | `ping_pong_router_and_player_a.py` | 47830, 47831 | 100 + 200 |
| Player B | `ping_pong_player_b.py` | 47833 | 200 |

`router-local.json` is loaded by terminal 1 (device **998**, networks **100** / **200**).

## Files

| File | Terminal |
|------|----------|
| `ping_pong_router_and_player_a.py` | 1 |
| `ping_pong_player_b.py` | 2 |
| `router-local.json` | used by terminal 1 |
