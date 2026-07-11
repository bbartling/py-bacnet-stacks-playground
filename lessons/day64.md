# Day 64 – Multi-Protocol Bench PCAP Challenge

## Goal

One capture, **three display filters**—BACnet UDP, Haystack HTTPS, Modbus TCP—document what each shows.

## Concept

```bash
PCAP_SECONDS=45 ./capture_pcap.sh day64-multi \
  "udp port 47808 or tcp port 443 or tcp port 1502"
```

Bench reference:

- BACnet: `192.168.204.200:47808`
- Haystack: `192.168.204.11:443`
- Modbus: `192.168.204.14:1502` (if enabled)

## Why This Matters

Open-FDD runs **multiple drivers**—one edge host, many transports (Day 35 map in production).

## Mini Examples

- IO graph per filter.
- Table: protocol, transport, port, tool that generated traffic.

## Micro Exercises

1. Three screenshots with three filters applied.
2. Which protocol is easiest to decode without TLS keys?
3. Write one sentence per protocol for your README portfolio.

## Key Takeaway

**Wireshark is multi-protocol**—display filters switch lenses on the same file.

## Wireshark Lab

Filters (apply one at a time):

1. `udp.port == 47808`
2. `tcp.port == 443 && ip.addr == 192.168.204.11`
3. `tcp.port == 1502`

---

## Python companion — Filter cheat sheet

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
# Capture/Wireshark are the lab—Python only documents lenses.
filters = {
    "bacnet": "udp.port == 47808",
    "haystack": "tcp.port == 443 && ip.addr == 192.168.204.11",
    "modbus": "tcp.port == 1502",
}
for name, f in filters.items():
    print(f"{name}: {f}")
```

| Rust (main lesson) | Python |
|--------|--------|
| Drivers generate traffic; pcap is shell | dict of display-filter strings |
| Three Wireshark lenses on one file | print a portfolio cheat sheet |

**Takeaway:** Multi-protocol means multiple filters—Python can list them; decode happens in Wireshark.
