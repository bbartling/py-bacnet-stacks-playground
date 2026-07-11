# Day 54 – Haystack Capstone: niagara-read Tool

## Goal

Ship a polished **`niagara-read`** (or your fork) with clap flags: URL, auth mode, filter, output format.

## Concept

Reference: [vibe_code_apps_17/nhaystack-niagara-pi-tutorial/](../vibe_code_apps_17/nhaystack-niagara-pi-tutorial/) (`nhaystack-smoke` CLI). Capstone pointer: [`capstone/niagara-read/`](./capstone/niagara-read/README.md).

Also see upstream `rusty-haystack/demo/niagara_sample/niagara-rusty-scrape/` when using the fork.

Flags to support:

- `--url`, `--user`, `--pass`
- `--auth basic|scram`
- `--filter 'point and temp'`
- `--probe-scram` diagnostic

## Why This Matters

This is the Rust/network capstone before RDF—HTTP + TLS + auth + parsing in one binary.

## Mini Examples

- JSON lines output for agent consumption (optional).
- Exit code non-zero on auth failure.

## Micro Exercises

1. README with example command for your bench.
2. Run tool in loop 10×—memory stable? (qualitative)
3. Add to vibe_code_apps_17 tutorial index.

## Wireshark Lab

One final Haystack capture during demo for portfolio zip.

## Key Takeaway

**Field-ready Haystack CLI in Rust**—network course outcome alongside BACnet capstone.

---

## Python companion — Thin read wrapper (conceptual)

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
# Conceptual — course deliverable is the Rust niagara-read CLI
import argparse
import requests

p = argparse.ArgumentParser()
p.add_argument("--url", default="https://192.168.204.11/haystack/about")
p.add_argument("--user"); p.add_argument("--pass")
args = p.parse_args()
r = requests.get(args.url, auth=(args.user, args.pass), verify=False, timeout=10)
raise SystemExit(0 if r.ok else 1)
```

| Rust (main lesson) | Python |
|--------|--------|
| clap `niagara-read` binary | argparse + requests sketch |
| `--filter` / Zinc parse | about GET only here |
| exit codes on auth fail | `SystemExit` on status |

**Takeaway:** Flag shapes can mirror in Python; the portfolio tool is rusty-haystack + Rust CLI.
