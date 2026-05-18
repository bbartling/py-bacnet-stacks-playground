# vibe_code_apps_14 — Campus BACnet routing lab

Single experiment: **flat campus** on `192.168.204.18:47808`, **three buildings** behind the router (mini + VAV + AHU Pis), deploy with Ansible, test from Windows.

**Tutorial (only test):** [docs/TUTORIAL-CAMPUS-LAB.md](docs/TUTORIAL-CAMPUS-LAB.md)

## Quick start

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_14/ansible
sudo apt install ansible-core sshpass rsync   # once on boss Pi
./deploy.sh
```

**Windows:** copy `scripts/campus_windows_probe.py`, then:

```powershell
pip install bacpypes3 ifaddr
python campus_windows_probe.py --campus 192.168.204.18
```

## Inventory

| Host | IP | Role |
|------|-----|------|
| bensserver | 192.168.204.18 | Router + mini (net 200 @ .28) |
| building_vav | 192.168.204.14 | fake_vav net 201 |
| building_ahu | 192.168.0.13 | fake_ahu net 202 |

SSH `ben` / `ben` — edit `ansible/group_vars/all.yml` if needed.
