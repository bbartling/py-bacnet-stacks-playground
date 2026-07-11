# Day 46 – BACnet Capstone: Mini Commission Tool

## Goal

Combine discovery + RPM + CSV log in one **`cargo` binary**—your Rust BACnet portfolio piece.

## Concept

Deliverable spec:

- Subcommand or flags: `discover`, `poll`
- Output: `commission_snapshot.csv` with columns `device,object,pv,timestamp`
- Graceful errors; no unwrap on network paths

**Tutorial starter:** [`capstone/discover-and-poll/`](./capstone/discover-and-poll/) — `cargo run -- discover` and `poll` stubs; wire [rusty-bacnet](https://github.com/jscott3201/rusty-bacnet) after Day 41. Lab hub: [vibe_code_apps_17/rust-lessons/](../vibe_code_apps_17/rust-lessons/README.md).

## Why This Matters

This mirrors **open-fdd** commissioning flows—Rust is how the edge crate implements them under the hood.

## Mini Examples

- Add `--device 5007` filter flag.
- Log to stderr, data to stdout (Unix tool hygiene).

## Micro Exercises

1. Run 5-minute poll; graph packet rate from pcap.
2. Peer review: can a tech run your binary with `--help` only?
3. Link to your vibe_code_apps Python equivalent—what improved?

## Wireshark Lab

Full bench capture during capstone:

```bash
./capture_pcap.sh day46-capstone "udp port 47808 or tcp port 443"
```

Filters: BACnet **`udp.port == 47808`**, Haystack **`tcp.port == 443`** — same file, two stories.

## Key Takeaway

**Small, reliable CLI tools** win in the field—Rust + Cargo + clap (optional) is a strong combo.

---

## Python companion — BACnet read sketch

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
# Conceptual BAC0 / bacpypes3 read — not the course deliverable
# import BAC0
# bacnet = BAC0.lite()
# pv = bacnet.read("5007:analogInput:1 presentValue")
# print(pv)
device, obj, pv, ts = 5007, "AI:1", 72.5, "2026-07-11T12:00:00Z"
print(f"{device},{obj},{pv},{ts}")  # same CSV shape as the Rust tool
```

| Rust (main lesson) | Python |
|--------|--------|
| `cargo` binary `discover` / `poll` | BAC0/bacpypes3 lab scripts |
| `commission_snapshot.csv` | same columns from a sketch print |
| rusty-bacnet + clap | optional Python Who-Is / RPM apps |

**Takeaway:** Python is fine for a quick read sketch; the portfolio CLI is the Rust capstone.
