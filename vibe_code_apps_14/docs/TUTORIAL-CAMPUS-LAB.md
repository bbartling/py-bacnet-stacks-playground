# Flat campus BACnet lab (Trane / Reddit style)

Mimics a **large flat IT LAN** where each building is isolated by **unique UDP port**, not by BACnet routing. This matches integrator pain points from real Trane/JCI/Siemens multi-building sites.

## Schematic

```text
                    FLAT IT LAN  192.168.204.0/24
                    (no BACnet router required)
                           |
         +-----------------+-----------------+-----------------+
         |                 |                 |                 |
         v                 v                 v                 v
   Windows SI         bensserver         Pi .14            Pi .13
   integrator         Trane              Siemens           JCI
   scrape             building           building          building
         |                 |                 |                 |
         |            :47809 front          :47810 front      :47811 front
         |            :47819 field*         :47820 field*     :47821 field*
         |            vendor 17             vendor 67         vendor 75
         +-------- unicast Who-Is / ReadProperty per port ---+

* field panel = mini-device behind the vendor front-end (second UDP port on same Pi)
```

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
