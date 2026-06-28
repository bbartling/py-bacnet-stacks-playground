# PCAP portfolio (Days 64 & 75)

Store captures from [../../lab-scripts/capture_pcap.sh](../../lab-scripts/capture_pcap.sh) here.  
**Do not commit secrets** — pcaps may contain credentials in TLS payloads; redact or keep local-only if unsure.

## Recommended capture

```bash
cd ../../lab-scripts
PCAP_IFACE=enp3s0 PCAP_SECONDS=45 ./capture_pcap.sh day75-final \
  "udp port 47808 or tcp port 443 or tcp port 1502"
mv ../../lab-scripts/../pcaps/day75-final_*.pcap ./   # or copy from lessons/pcaps/
```

## Wireshark display filters (paste one at a time)

| Protocol | Filter | What you should see |
|----------|--------|---------------------|
| BACnet/IP | `udp.port == 47808` | BVLC / Who-Is / ReadProperty |
| Haystack HTTPS | `tcp.port == 443 && ip.addr == 192.168.204.11` | TLS handshake; app data encrypted |
| Modbus TCP | `tcp.port == 1502` | Modbus ADU (if bench Modbus active) |

Full cheat sheet: [../../lab-scripts/wireshark_filters.md](../../lab-scripts/wireshark_filters.md)

## Your notes (fill in)

### Capture 1 — BACnet

- File:
- Filter used:
- One sentence:

### Capture 2 — Haystack

- File:
- Filter used:
- One sentence:

### Capture 3 — Multi-protocol (Day 64)

- File:
- Filters tried:
- Screenshot path (optional):
