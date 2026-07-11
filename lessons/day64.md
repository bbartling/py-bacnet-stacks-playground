# Day 64 – Multi-Protocol Bench PCAP Challenge

*Part VII: RDF & Brick | Week 12*

## Goal

One capture, **three display filters**—BACnet UDP, Haystack HTTPS, Modbus TCP—document what each shows. Light dual-stack notes only.

## Concept

```bash
PCAP_SECONDS=45 ./capture_pcap.sh day64-multi \
  "udp port 47808 or tcp port 443 or tcp port 1502"
```

Bench reference:

- BACnet: `192.168.204.200:47808`
- Haystack: `192.168.204.11:443`
- Modbus: `192.168.204.14:1502` (if enabled)

RDF tie-in (thin): each protocol eventually feeds points that land in the same Brick graph (`ex:` / `brick:hasPoint`) from Days 58–63.

## Why This Matters

Open-FDD runs **multiple drivers**—one edge host, many transports.

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

## Python companion — Filter cheat sheet (+ RDF hint)

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
# Capture/Wireshark are the lab—aligned labels for portfolio.
filters = {
    "bacnet": "udp.port == 47808",
    "haystack": "tcp.port == 443 && ip.addr == 192.168.204.11",
    "modbus": "tcp.port == 1502",
}
# Later: map decoded points → ex: / brick:hasPoint (Days 58–63)
for name, f in filters.items():
    print(f"{name}: {f}")
```

| Rust (main lab) | Python |
|--------|--------|
| Drivers generate traffic; pcap is shell | dict of display-filter strings |
| Three Wireshark lenses | same three names |
| RDF graph is yesterday's model | same `ex:` / `brick:` story |

**Takeaway:** Multi-protocol means multiple filters—semantics reunite them in the Brick graph.
