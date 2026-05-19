# vibe_code_apps_14 — Flat campus BACnet lab

Simulates a **Trane-style flat LAN**: each building on a **unique UDP port**, different **vendor IDs** (Trane / Siemens / JCI), plus a **field-panel mini** on a second port per site.

**Tutorial:** [docs/TUTORIAL-CAMPUS-LAB.md](docs/TUTORIAL-CAMPUS-LAB.md)

## Schematic

```text
  Windows integrator                    FLAT 192.168.204.0/24
        |                                        |
        +--- scrape 192.168.204.18:47809  Trane (9001 + field :47819)
        +--- scrape 192.168.204.14:47810  Siemens VAV (3456790 + :47820)
        +--- scrape 192.168.204.13:47811  JCI AHU (3456789 + :47821)
```

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

| Host | IP | Building ports |
|------|-----|----------------|
| bensserver | 192.168.204.18 | 47809, 47819 |
| building_vav | 192.168.204.14 | 47810, 47820 |
| building_ahu | 192.168.204.13 | 47811, 47821 |

SSH `ben` / `ben` — `ansible/group_vars/all.yml`

After deploy, each Pi has **`bacnet.pcap`** (60s, overwritten) for Wireshark.
