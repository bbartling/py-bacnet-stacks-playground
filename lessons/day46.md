## Day 46 – BACnet Capstone: Mini Commission Tool

### Goal

Combine discovery + RPM + CSV log in one **`cargo` binary**—your Rust BACnet portfolio piece.

### Concept

Deliverable spec:

- Subcommand or flags: `discover`, `poll`
- Output: `commission_snapshot.csv` with columns `device,object,pv,timestamp`
- Graceful errors; no unwrap on network paths

**Tutorial starter:** [`capstone/discover-and-poll/`](./capstone/discover-and-poll/) — `cargo run -- discover` and `poll` stubs; wire [rusty-bacnet](https://github.com/jscott3201/rusty-bacnet) after Day 41. Lab hub: [vibe_code_apps_17/rust-lessons/](../vibe_code_apps_17/rust-lessons/README.md).

### Why This Matters

This mirrors **open-fdd** commissioning flows—Rust is how the edge crate implements them under the hood.

### Mini examples

- Add `--device 5007` filter flag.
- Log to stderr, data to stdout (Unix tool hygiene).

### Micro exercises

1. Run 5-minute poll; graph packet rate from pcap.
2. Peer review: can a tech run your binary with `--help` only?
3. Link to your vibe_code_apps Python equivalent—what improved?

### Key takeaway

**Small, reliable CLI tools** win in the field—Rust + Cargo + clap (optional) is a strong combo.

### Wireshark Lab

Full bench capture during capstone:

```bash
./capture_pcap.sh day46-capstone "udp port 47808 or tcp port 443"
```

Filters: BACnet **`udp.port == 47808`**, Haystack **`tcp.port == 443`** — same file, two stories.
