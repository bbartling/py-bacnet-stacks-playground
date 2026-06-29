# vibe_code_apps_14 — BACnet routing research lab

**Status:** Planned — checkpoint **14** (research lab content preserved; not an active featured build).

Simulates a **Trane-style flat LAN**: each building on a **unique UDP port**, different **vendor IDs** (Trane / Siemens / JCI), plus a **field-panel mini** on a second port per site.

**Tutorial:** [docs/TUTORIAL-CAMPUS-LAB.md](docs/TUTORIAL-CAMPUS-LAB.md)

## Schematic

Each **building** = same Pi IP, **two UDP ports** (front + field panel). No BACnet router.

```text
  Windows integrator          FLAT LAN 192.168.204.0/24  (unicast Who-Is / Read per port)
        |
        |  TRANE building — bensserver 192.168.204.18
        +--- :47809  front   device 9001   (mini, vendor Trane)
        +--- :47819  field   device 1001   (mini, field panel)
        |
        |  SIEMENS building — Pi 192.168.204.14
        +--- :47810  front   device 3456790  (fake_vav, vendor Siemens)
        +--- :47820  field   device 1101     (mini, field panel)
        |
        |  JCI building — Pi 192.168.204.13
        +--- :47811  front   device 3456789  (fake_ahu, vendor JCI)
        +--- :47821  field   device 1102     (mini, field panel)
```

Field ports are **front port + 10** on the same IP (47809→47819, 47810→47820, 47811→47821).

## One-command deploy

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_14/ansible
./deploy.sh
```

## Windows test

```powershell
pip install bacpypes3 ifaddr pyyaml
python campus_integrator_scrape.py --config campus_buildings.yml
```

Copy `scripts/campus_integrator_scrape.py` and `config/campus_buildings.yml` to the laptop.

## Inventory

| Host | IP | Front port (vendor) | Field port (mini) |
|------|-----|---------------------|-------------------|
| bensserver | 192.168.204.18 | 47809 | 47819 |
| building_vav | 192.168.204.14 | 47810 | 47820 |
| building_ahu | 192.168.204.13 | 47811 | 47821 |

SSH `ben` / `ben` — `ansible/group_vars/all.yml`

After deploy, each Pi has **`bacnet.pcap`** (60s, overwritten) for Wireshark.

## Same PC — ping-pong read/write labs

| Lab | Terminals | Mechanism |
|-----|-----------|-----------|
| [run_two_on_same_pc](run_two_on_same_pc/README.md) | 2 | Direct `IP:port` ReadProperty (no router) |
| [run_two_on_same_pc_router](run_two_on_same_pc_router/README.md) | 2 | BACnet nets **100/200** via `ping_pong_router_and_player_a.py` |
