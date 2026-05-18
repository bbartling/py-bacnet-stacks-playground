# Remote discovery (second PC on the LAN)

Lab server example: **`192.168.204.18`** (replace with your `HOST_IP`).

## Firewall on the lab server

Allow **UDP** from your subnet to:

| Port | When |
|------|------|
| 47809, 47810 | `minis` timed lab |
| 47808, 47809 | `router` timed lab |
| 47812 | optional client bind for probe scripts |

```bash
sudo ufw allow from 192.168.204.0/24 to any port 47808:47812 proto udp
```

## Mode: two minis (`./scripts/run_timed_lab.sh minis`)

Devices listen on **non-standard** BACnet/IP ports:

| Device | Instance | Target |
|--------|----------|--------|
| MiniA | 1001 | `192.168.204.18:47809` |
| MiniB | 1002 | `192.168.204.18:47810` |

### From another PC — **yes, with unicast**

Standard **Who-Is broadcast to UDP 47808** will **not** find them.

**Option A — copy probe script** (needs Python + bacpypes3 on remote PC):

```bash
git clone ... # same repo or copy scripts/discover_minis_unicast.py
pip install bacpypes3
export HOST_IP=192.168.204.18   # lab server, not localhost
python discover_minis_unicast.py --host "$HOST_IP" --client-port 47813
```

**Option B — YABE / VTS**

Add devices by **explicit IP:port** (if the tool supports non-47808 binds), or use a BACpypes3 client with:

```text
destination 192.168.204.18:47809
Who-Is 1001 1001
```

### Wireshark on remote PC

You can capture on the remote NIC while the lab runs; you should see **unicast** BACnet/IP between your PC and `.18:47809`/`:47810` when you run the probe.

## Mode: ipv4 router (`./scripts/run_timed_lab.sh router`)

Router binds:

| Port | BACnet network |
|------|----------------|
| 47808 | 100 |
| 47809 | 200 |

### From another PC

| Goal | Works? | How |
|------|--------|-----|
| See router device **998** | **Yes** | Unicast Who-Is to `SERVER:47808` |
| See minis on 47809/47810 **through** router | **Not in minis-only lab** | Need devices on nets 100/200 behind router (two-machine Lab C) |
| Standard broadcast discovery | **Limited** | Broadcast is port-specific; use `47808` for net-100 leg |

Route-aware form (when remote devices exist on nets 100/200):

```text
100:1001@192.168.204.18
200:1002@192.168.204.18
```

## Timed lab + pcap

On the **server**:

```bash
sudo ./scripts/run_timed_lab.sh minis
# or
sudo ./scripts/run_timed_lab.sh router
```

Produces `captures/<timestamp>-<mode>-60s.pcap` — safe to commit for learning (small files).

On the **remote PC** during those 60s, run the LAN probe (Who-Is + read simulated sensor):

```bash
pip install bacpypes3 ifaddr
python remote_read_minis.py --server 192.168.204.18
```

Script path: `scripts/remote_read_minis.py` — see `scripts/README-remote-probe.md`. Your laptop’s IP will show up in the server pcap as unicast to `:47809` / `:47810`.

## Quick checklist

- [ ] Remote PC on same LAN / routed subnet  
- [ ] Server `ufw` allows UDP 47808–47812  
- [ ] Use **server IP**, not `localhost`  
- [ ] For minis: target **:47809** and **:47810**, not only :47808  
