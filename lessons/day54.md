## Day 54 – Haystack Capstone: niagara-read Tool

### Goal

Ship a polished **`niagara-read`** (or your fork) with clap flags: URL, auth mode, filter, output format.

### Concept

Reference: [vibe_code_apps_17/nhaystack-niagara-pi-tutorial/](../vibe_code_apps_17/nhaystack-niagara-pi-tutorial/) (`nhaystack-smoke` CLI). Capstone pointer: [`capstone/niagara-read/`](./capstone/niagara-read/README.md).

Also see upstream `rusty-haystack/demo/niagara_sample/niagara-rusty-scrape/` when using the fork.

Flags to support:

- `--url`, `--user`, `--pass`
- `--auth basic|scram`
- `--filter 'point and temp'`
- `--probe-scram` diagnostic

### Why This Matters

This is the Rust/network capstone before RDF—HTTP + TLS + auth + parsing in one binary.

### Mini examples

- JSON lines output for agent consumption (optional).
- Exit code non-zero on auth failure.

### Micro exercises

1. README with example command for your bench.
2. Run tool in loop 10×—memory stable? (qualitative)
3. Add to vibe_code_apps_17 tutorial index.

### Key takeaway

**Field-ready Haystack CLI in Rust**—network course outcome alongside BACnet capstone.

### Wireshark Lab

One final Haystack capture during demo for portfolio zip.
