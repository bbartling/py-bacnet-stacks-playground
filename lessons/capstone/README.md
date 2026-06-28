# Rust course capstone (Days 46, 54, 75)

Turn-key starter tree for the **Days 28–75** track after Python Day 27. Complete the daily lessons first; use this folder as your **portfolio bundle**.

## Layout

| Path | Lesson | What you ship |
|------|--------|----------------|
| [discover-and-poll/](discover-and-poll/) | Day **46** | BACnet discovery + poll → `commission_snapshot.csv` |
| [../vibe_code_apps_17/nhaystack-niagara-pi-tutorial/](../../vibe_code_apps_17/nhaystack-niagara-pi-tutorial/) | Day **54** | Haystack CLI (`nhaystack-smoke`) — mature tutorial |
| [model/ahu1.ttl](model/ahu1.ttl) | Day **62** | Hand-authored Brick model (extend it) |
| [graph-export/](graph-export/) | Days **66**, **68**, **75** | Load TTL + stub BACnet → merged Turtle |
| [pcaps/README.md](pcaps/README.md) | Days **64**, **75** | Wireshark filters for your captures |
| [COURSE_REVIEW.md](COURSE_REVIEW.md) | Day **74** | One-page architecture doc template |

## Bench environment (example)

Copy [env.example](env.example) to `.env` (gitignored if you put secrets in it):

```bash
source env.example   # edit IPs/creds first
```

| Service | Address |
|---------|---------|
| Edge NIC | `192.168.204.55` |
| BACnet device **5007** | `192.168.204.200` UDP **47808** |
| Niagara nHaystack | `https://192.168.204.11/haystack` |
| Modbus (optional PCAP) | `192.168.204.14:1502` |

## Quick start

```bash
# Day 46 — BACnet capstone skeleton
cd discover-and-poll
cargo run -- discover --bind 0.0.0.0:47808
cargo run -- poll --device 5007 --out commission_snapshot.csv

# Day 54 — Haystack (full tutorial)
cd ../../vibe_code_apps_17/nhaystack-niagara-pi-tutorial
cp env.example .env   # edit password
cargo run -- --about
cargo run -- --filter 'point and temp'

# Day 75 — graph export
cd ../../lessons/capstone/graph-export
cargo run -- --ttl ../model/ahu1.ttl --out merged.ttl
```

## Wireshark captures

From [../lab-scripts/capture_pcap.sh](../lab-scripts/capture_pcap.sh):

```bash
cd ../lab-scripts
PCAP_IFACE=enp3s0 ./capture_pcap.sh day75-final \
  "udp port 47808 or tcp port 443 or tcp port 1502"
```

Paste filters from [../lab-scripts/wireshark_filters.md](../lab-scripts/wireshark_filters.md) into your [pcaps/README.md](pcaps/README.md).

## Lesson links

- [Day 46](../day46.md) · [Day 54](../day54.md) · [Day 75](../day75.md)
- [Lessons INDEX](../INDEX.md) · [Repo weekly outline](../../README.md#computer-science-theory-101-weekly-outline)
- [vibe_code_apps_17 Rust lab hub](../../vibe_code_apps_17/rust-lessons/README.md)

## Wiring rusty-bacnet (Day 46+)

The `discover-and-poll` crate ships with **UDP placeholders** so `cargo build` works without cloning [rusty-bacnet](https://github.com/jscott3201/rusty-bacnet). When you reach Day 41:

1. Clone rusty-bacnet and run its examples against device **5007**.
2. Replace `src/discover.rs` / `src/poll.rs` TODO blocks with stack API calls.
3. Optional: add a `[patch]` or path dependency in `Cargo.toml`.

Same pattern for **rusty-haystack** on Day 49 — start from `nhaystack-niagara-pi-tutorial` instead of reinventing HTTP/TLS.
