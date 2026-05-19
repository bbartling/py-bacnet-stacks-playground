# Flat campus BACnet lab (Trane / Reddit style)

Mimics a **large flat IT LAN** where each building is isolated by **unique UDP port**, not by BACnet routing. This matches integrator pain points from real Trane/JCI/Siemens multi-building sites.

## Schematic

```text
  FLAT IT LAN 192.168.204.0/24 — no BACnet router; integrator uses unicast per IP:port

  Windows integrator
        |
        |  192.168.204.18  TRANE (bensserver)
        +-- :47809  front  device 9001   mini, vendor Trane (17)
        +-- :47819  field  device 1001   mini, field panel
        |
        |  192.168.204.14  SIEMENS
        +-- :47810  front  device 3456790  fake_vav, vendor Siemens (67)
        +-- :47820  field  device 1101     mini, field panel
        |
        |  192.168.204.13  JCI
        +-- :47811  front  device 3456789  fake_ahu, vendor JCI (75)
        +-- :47821  field  device 1102     mini, field panel
```

Six scrapes total (two per Pi). Field UDP port = front port + 10 on the **same** IP.

Duplicate device instances across buildings are OK on this bench because each building is a separate **IP:port** island (same as the Reddit thread — Niagara hates it if you treat them as one broadcast domain).

## Building table

| Building | IP | Front UDP | Vendor | Front device | Field UDP | Field device |
|----------|-----|-----------|--------|--------------|-----------|--------------|
| Trane Hall | 192.168.204.18 | **47809** | Trane (17) | 9001 mini | 47819 | 1001 mini |
| Siemens VAV | 192.168.204.14 | **47810** | Siemens (67) | 3456790 fake_vav | 47820 | 1101 mini |
| JCI AHU | 192.168.204.13 | **47811** | JCI (75) | 3456789 fake_ahu | 47821 | 1102 mini |

All use **BACnet network 0** (default) on each UDP socket.

Config source of truth: `config/campus_buildings.yml`

## Deploy (one command)

From **bensserver**:

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_14/ansible
sudo apt install ansible-core sshpass rsync   # once
./deploy.sh
```

- Pushes lab to each Pi, starts systemd units, runs **60s tcpdump** → overwrites `bacnet.pcap` for Wireshark.
- bensserver uses the live git tree; Pis use `~/vibe_code_apps_14/`.

## Windows — systems integrator scrape

Copy to laptop:

- `scripts/campus_integrator_scrape.py`
- `config/campus_buildings.yml`

```powershell
pip install bacpypes3 ifaddr pyyaml
python campus_integrator_scrape.py --config campus_buildings.yml
```

The script **unicast Who-Is** to each building’s `IP:port`, prints **vendor ID**, then **ReadProperty** on a sample point — like polling 30 buildings on 30 UDP ports.

Standard **broadcast Discover on :47808** will **not** see buildings on :47809+.

## Stop

```bash
./scripts/stop_lab.sh
# or per host: sudo systemctl stop 'campus-bldg-*'
```
