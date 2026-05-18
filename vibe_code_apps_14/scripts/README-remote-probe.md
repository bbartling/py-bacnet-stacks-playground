# Remote LAN probe (second computer)

## What this proves

While `sudo ./scripts/run_timed_lab.sh minis` runs on **bensserver**, run from your laptop:

```bash
pip install bacpypes3 ifaddr
python remote_read_minis.py --server 192.168.204.18
```

You should see **Who-Is / I-Am** and **present-value** on `analog-value,1` (simulated temperature) for **both** MiniA and MiniB.

That confirms **LAN reachability + BACnet on non-standard ports**. It does **not** test BACnet **routing** (no router in the minis lab).

## Copy to Windows

Minimal copy — only this file:

- `scripts/remote_read_minis.py`

Or clone the repo and use `vibe_code_apps_14/scripts/`.

## Firewall (bensserver)

```bash
sudo ufw allow from 192.168.204.0/24 to any port 47809:47812 proto udp
```

## During the 60s capture

1. **Server:** `sudo ./scripts/run_timed_lab.sh minis`
2. **Laptop:** `python remote_read_minis.py --server 192.168.204.18`
3. Open the new `.pcap` on the server — you should see **your laptop’s IP** → `.18:47809` / `:47810`.

## Routing lab (later)

Use `run_timed_lab.sh router` plus two-machine layout in `docs/TUTORIAL-bacnet-routing-research.md` § Lab C.
