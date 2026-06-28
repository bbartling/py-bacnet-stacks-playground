## Day 38 – tcpdump & PCAP Workflow

### Goal

Master the **capture → file → Wireshark** loop you'll reuse for BACnet and Haystack labs.

### Concept

```bash
# 30s BACnet bench capture (adjust host)
sudo tcpdump -i any -w bacnet.pcap -s 0 'udp port 47808'

# Read without GUI
tcpdump -r bacnet.pcap -c 5 -n
```

Our helper:

```bash
cd lessons/lab-scripts
PCAP_SECONDS=15 PCAP_IFACE=enp3s0 ./capture_pcap.sh day38-bench "udp port 47808 or tcp port 443"
```

**`-s 0`**: full snaplen—don't truncate BACnet payloads.

**`-n`**: no DNS—show IPs.

### Why This Matters

Commissioning without pcaps is guessing. Techs who can capture once and analyze offline win arguments about routing and firewalls.

### Mini examples

- Capture only host `192.168.204.200`.
- File size sanity: 30s BACnet on quiet net ≈ small MB.

### Micro exercises

1. Run capture script during a Python or rusty Who-Is—did you get packets?
2. What does "promiscuous mode" mean in one sentence?
3. Store pcaps under `lessons/pcaps/` with dated names—practice good hygiene.

### Key takeaway

**tcpdump writes truth**—Wireshark is the microscope.

### Wireshark Lab

Open your `day38-bench_*.pcap`.

Try display filters in order:

1. `udp or tcp`
2. `udp.port == 47808`
3. `tcp.port == 443`

Paste filter results count into lab notes (View → Packet List applies filter).
