# Campus BACnet lab (only test for vibe_code_apps_14)

One head-end router on **bensserver**, three building devices, one Windows laptop on the flat campus.

## Schematic

```text
                    FLAT CAMPUS (BACnet/IP)
                    Who-Is / Discover :47808
                           |
    +----------------------+----------------------+
    |                      |                      |
    v                      v                      v
 Windows PC          192.168.204.18         (same LAN)
 (campus client)     bensserver
                     +-- campus-router :47808  BACnet net 100  device 998
                     |       |
                     |       +-- net 200 --> 192.168.204.28:47809  mini 1001
                     |       +-- net 201 --> 192.168.204.14:47808  VAV 3456790
                     |       +-- net 202 --> 192.168.0.13:47808    AHU 3456789
                     |
                     +-- campus-mini @ .28:47809

  building_vav Pi              building_ahu Pi
  192.168.204.14               192.168.0.13
  fake_vav.py net 201          fake_ahu.py net 202
```

Routed reads from Windows use **one** campus IP:

```text
200:1001@192.168.204.18
201:3456790@192.168.204.18
202:3456789@192.168.204.18
```

## Device table

| Name | Host | BACnet net | Instance | UDP | Sample |
|------|------|------------|----------|-----|--------|
| Campus router | 192.168.204.18 | 100 | 998 | 47808 | router JSON |
| Building mini | 192.168.204.28 | 200 | 1001 | 47809 | mini-device-revisited.py |
| Bens fake VAV | 192.168.204.14 | 201 | 3456790 | 47808 | fake_vav.py |
| Bens fake AHU | 192.168.0.13 | 202 | 3456789 | 47808 | fake_ahu.py |

**Note:** AHU is on `192.168.0.0/24`. Uncomment `building_ahu` in `ansible/inventory.yml` and set `deploy_ahu: true` in `group_vars/all.yml` when the boss Pi can SSH to `192.168.0.13`. Until then the router still advertises net **202**; Windows probes for the AHU will fail until that Pi is online.

## Deploy (boss Pi)

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_14/ansible
sudo apt install ansible-core sshpass rsync   # once
chmod +x deploy.sh ../scripts/*.sh
./deploy.sh
```

SSH: user `ben`, password `ben` (see `group_vars/all.yml`).

Each Pi overwrites **`~/vibe_code_apps_14/bacnet.pcap`** with a **60s** BACnet-only capture after deploy.

## Windows test

Copy one file to the laptop:

- `scripts/campus_windows_probe.py`

```powershell
pip install bacpypes3 ifaddr
python campus_windows_probe.py --campus 192.168.204.18
```

Expect:

1. **I-Am-Router-To-Network** listing networks **100, 200, 201, 202**
2. **I-Am** + **ReadProperty** for mini, VAV, and AHU

Optional: BACnet scan on `192.168.204.18:47808` shows the **router (998)** only; building devices appear via **routing**, not campus broadcast.

## Stop lab

On each Pi:

```bash
sudo systemctl stop campus-router campus-mini campus-bacnet-device
```

Or re-run `./scripts/stop_lab.sh` on bensserver.

## Files

| Path | Role |
|------|------|
| `ansible/deploy_campus_lab.yml` | Full deploy |
| `config/campus-full-router.template.json` | Router nets 100–202 |
| `scripts/campus_windows_probe.py` | Windows test script |
| `samples/fake_ahu.py` / `fake_vav.py` | Building controllers |
