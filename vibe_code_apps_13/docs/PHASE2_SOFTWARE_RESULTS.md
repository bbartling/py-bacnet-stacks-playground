# Phase 2 — Software results (loopback / CI)

**Date:** 2026-08-28  
**rusty-bacnet pin:** `c77f78445fbf40da15867fec28a36ea120ad1739`  
**Hardware evidence:** **NOT RUN** (USB RS-485 adapters are not installed/wired)

## Passed software checks

| Check | Result |
|-------|--------|
| `cargo fmt --all -- --check` | PASS |
| `cargo clippy --workspace --all-targets --locked -- -D warnings` | PASS |
| `cargo test --workspace --locked` | PASS |
| `./scripts/check_mstp_no_ip.sh` (local source markers) | PASS |
| `mstp-probe --profile smoke … loopback` | PASS (`hardware_evidence=false`) |
| Baud propagation unit tests (all 6 rates) | PASS |
| Gate report completeness unit tests | PASS |
| Vendor ID consistency in Device object | PASS |
| Local AI/BI simulation via `set_present_value` + network WP denied | PASS |
| Streamlit AppTest (Phase 2 buttons present) | PASS (CI) |

## Loopback evidence

Loopback runs a full application-service sequence on `LoopbackSerial`:

- Who-Is → require I-Am for instance + MAC + vendor
- Device Object_Name + Object_List (Device + AI:1 + BI:1 + AV:2 + BV:2)
- RP AI/BI, RPM, WP/relinquish AV:2 + BV:2
- Unknown object + write-access denial on AI:1
- Repeated reads with latency summary
- Clean client/server stop

Reports use schema `phase2_acceptance_v2` with `profile`, `hardware_evidence=false` for loopback.

Artifact example: `captures/mstp-loopback-software.json` / CI `captures/mstp-loopback-ci.json`.

## Hardware NOT RUN

Phase 2 USB RS-485 adapters are **not installed or wired** on this host.

- Do not treat loopback PASS as hardware gate PASS.
- See [`PHASE2_HARDWARE_RUNBOOK.md`](PHASE2_HARDWARE_RUNBOOK.md) for the exact human bench commands (placeholders only).

## Known rusty-bacnet / upstream blockers

| Topic | Status |
|-------|--------|
| Transitive `socket2` via `bacnet-transport` even with `features=["serial"]` | **BLOCKED** dependency-level isolation on this pin — documented by `check_mstp_no_ip.sh` / `captures/phase2-no-ip-gate-status.txt`. Runtime still opens no IP sockets. Upstream ask: split serial-only builds from B/IP/socket2. |
| `BACnetServer` transport-death notification | **Gap** — pin exposes `stop()` but no public “transport task died” waiter. Apps wait for SIGINT/SIGTERM only. |
| Lab vendor ID `999` | Placeholder only — not production-ready. |

## Remaining gate work (requires hardware)

- Smoke + gate profiles on real dual Waveshare C adapters
- Startup-order / sole-master / duplicate-MAC / baud-mismatch / unplug
- 500-read gate + one-hour soak + per-baud matrix

## Profiles

| Profile | `repeated_reads` | Required steps |
|---------|------------------|----------------|
| `smoke` | small (CI default 5–10) | Full service coverage; zero failures |
| `gate` | ≥ 500 | Every `GATE_REQUIRED_STEPS` present and ok |
