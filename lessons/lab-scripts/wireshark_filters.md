# Wireshark display filters — Rust networking course cheat sheet

Use in **View → Filter toolbar** (display filter, not capture filter).

| Lesson | What you captured | Paste this filter |
|--------|-------------------|-------------------|
| Day 36 | UDP echo lab | `udp` |
| Day 36b | Modbus TCP (bench PLC) | `modbus` or `tcp.port == 1502` |
| Day 38 | General bench | `udp or tcp` |
| Day 39 | BACnet on LAN | `udp.port == 47808` |
| Day 40 | BACnet + follow | `bacnet` or `udp.port == 47808` |
| Day 44 | Who-Is / I-Am | `udp.port == 47808 && bacnet` |
| Day 52 | Haystack HTTPS | `tcp.port == 443` |
| Day 53 | TLS handshake | `tls.handshake.type == 1` |
| Day 54 | HTTP inside TLS | `http` (after Follow → TLS stream) |
| Day 64 | Multi-protocol bench | `udp.port == 47808 or tcp.port == 443 or tcp.port == 1502` |

## Quick tips

1. **Capture filter** (tcpdump `-f`): limits what is saved. **Display filter**: what you see after opening the file.
2. Right-click a packet → **Follow → UDP Stream** or **Follow → TCP Stream** for conversational view.
3. **Statistics → Conversations** shows who talked to whom.
4. BACnet often appears as **BVLC** then **NPDU** in the packet details tree.

## tcpdump capture examples

```bash
cd lessons/lab-scripts
./capture_pcap.sh day36b-modbus "tcp port 1502 or tcp port 502"
./capture_pcap.sh day39-bacnet "udp port 47808"
./capture_pcap.sh day52-haystack "tcp port 443 and host 192.168.204.11"
```
