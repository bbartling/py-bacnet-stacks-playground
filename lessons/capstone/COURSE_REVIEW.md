# Course review (Day 74 template)

Fill this in after completing Days 28–73. One page is enough.

## What I kept from Python (Days 1–27)

- BACnet concepts that still apply in Rust:
- Python tools I still use alongside Rust:

## Network programming wins

- UDP vs TCP — one sentence each for my bench:
- Wireshark filters I used most often:
- Best pcap filename / what it proved:

## rusty-bacnet

- Device / object I read successfully:
- What failed once and what the pcap showed:

## rusty-haystack

- Auth mode on my Niagara station (Basic / SCRAM):
- Tutorial path used (`nhaystack-niagara-pi-tutorial` / fork):

## RDF in Rust

- Triple count in `model/ahu1.ttl`:
- One query I implemented by hand (describe pattern):
- Haystack tags vs Brick — when I'd pick each:

## Architecture sketch

```text
[ edge host ] ──UDP 47808──► BACnet device 5007
              ──TCP 443───► Niagara /haystack
              ──TTL graph─► FDD / agents (future)
```

## Next steps

- Open-FDD driver wiring / MCP:
- PR or portfolio link:
