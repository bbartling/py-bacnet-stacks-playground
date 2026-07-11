# Day 39 – Wireshark: BACnet on UDP

## Goal

Read **BVLC → NPDU → APDU** layers in Wireshark for a real **ReadProperty** or **Who-Is** capture.

## Concept

Display filter cheat sheet (see [wireshark_filters.md](./lab-scripts/wireshark_filters.md)):

```
udp.port == 47808
bacnet
bacnet.type == 0x10   # Who-Is (example; verify in your capture)
```

Packet details tree:

- **Ethernet / IP / UDP**
- **BACnet Virtual Link Control (BVLC)**
- **Network Layer (NPDU)**
- **Application Layer (APDU)**

## Why This Matters

When rusty-bacnet returns an error, the pcap tells you if the problem is **network** (no reply) or **application** (Error PDU).

## Mini Examples

- Identify source/dest IP and UDP ports on one BACnet packet.
- Export one packet as hex and compare to Rust `&[u8]` buffer mindset.

## Micro Exercises

1. Capture during `Who-Is`—find **I-Am** in the list.
2. Apply filter `bacnet && ip.addr == 192.168.204.200` (adjust IP).
3. Screenshot one ReadProperty decode for your portfolio.

## Key Takeaway

**Filter `udp.port == 47808` first**, then narrow with `bacnet.*` fields.

## Wireshark Lab

```bash
./capture_pcap.sh day39-bacnet "udp port 47808 and host 192.168.204.200"
```

While capturing, trigger a BACnet read from any tool you have.

In Wireshark: **`udp.port == 47808 && bacnet`**

---

## Python companion — BACnet capture helpers

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab` (create if needed).*

```python
# Trigger traffic in Python; decode in Wireshark (filters unchanged)
# import BAC0
# bacnet = BAC0.lite()
# bacnet.whois()                    # while capture_pcap.sh is running
FILTERS = [
    "udp.port == 47808",
    "bacnet",
    "bacnet && ip.addr == 192.168.204.200",
]
print("Apply in Wireshark:", FILTERS[0], "then narrow with bacnet.*")
```

| Rust (main lesson) | Python |
|--------|--------|
| BVLC → NPDU → APDU in GUI | identical pcap layers |
| rusty-bacnet for traffic | BAC0 / BACpypes3 to generate packets |
| filter `udp.port == 47808` | same display filters |
| hex ↔ `&[u8]` mindset | hex ↔ `bytes` mindset |

**Takeaway:** Who-Is from Python, layers from Wireshark—when the stack errors, the pcap still decides network vs APDU.
