# Two BACpypes3 apps on one PC (ping-pong)

Two **separate scripts**, two **UDP ports**, one **commandable** `analog-value,1` each. They read each other with **ReadProperty** and bump a counter — **no BACnet routing**, just direct `IP:port` unicast.

Read/write style matches `../../vibe_code_apps_1/bacpypes3_version_1.py`.

## Schematic

```text
  Same computer, one LAN IP, two UDP ports

  Terminal 1                    Terminal 2
  ping_pong_player_a.py         ping_pong_player_b.py
  192.168.204.18:47809          192.168.204.18:47810
  device 1001  "pong"  <----->  device 1002  "pong"
```

## Before you start

1. Install once:

   ```bash
   pip install bacpypes3 ifaddr
   ```

2. Edit **`HOST_IP`** at the top of **both** `.py` files if your PC is not `192.168.204.18`:
   - Windows: `ipconfig`
   - Linux: `hostname -I`

3. Use **`/24` in the bind** (`HOST_IP/24:port`) so BACnet/IP works reliably on Windows.

## Run in two terminals (manual)

Start **A first** (it serves the first `1` when both counters are at 0). Leave each terminal running; press **Ctrl+C** to stop.

### Linux

**Terminal 1**

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_14/run_two_on_same_pc
python3 ping_pong_player_a.py
```

**Terminal 2**

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_14/run_two_on_same_pc
python3 ping_pong_player_b.py
```

### Windows (PowerShell or Command Prompt)

**Terminal 1**

```powershell
cd py-bacnet-stacks-playground\vibe_code_apps_14\run_two_on_same_pc
python ping_pong_player_a.py
```

**Terminal 2**

```powershell
cd py-bacnet-stacks-playground\vibe_code_apps_14\run_two_on_same_pc
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

At **100**, each side resets its local `pong` to `0` and the rally starts again.

## Hard-coded settings

| | Player A (`ping_pong_player_a.py`) | Player B (`ping_pong_player_b.py`) |
|--|-------------------------------------|-------------------------------------|
| UDP port | 47809 | 47810 |
| Device instance | 1001 | 1002 |
| Starter (first hit at 0:0) | yes | no |

## Files

| File | Run in |
|------|--------|
| `ping_pong_player_a.py` | Terminal 1 |
| `ping_pong_player_b.py` | Terminal 2 |
