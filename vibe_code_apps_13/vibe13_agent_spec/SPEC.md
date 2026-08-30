# Vibe13 — BACnet MS/TP router lab (agent spec)

**Checkpoint:** `vibe_code_apps_13`  
**Mission:** Evidence-gated path from raw RS-485 bytes → `rusty-bacnet` MS/TP device → B/IP↔MS/TP router appliance.  
**Primary agent contract:** [`../AGENTS.md`](../AGENTS.md)

## UI stack decision (canonical)

**Yes — Streamlit for the lab now; Rust web for the appliance later.** That split matches how Metasys/Niagara/Siemens supervisory UIs work vs field tools: Python UI on the bench, Rust on the box.

| Layer | Phase | Technology | Where it runs |
|-------|-------|------------|---------------|
| Lab supervisory console | 1–2 | **Streamlit** (`tools/supervisory_console.py`) | bensbench — commissioning only |
| Hardware / protocol engine | 1–3 | **Rust** (`serial-wire-test`, later `rusty-bacnet`) | Same bench; Phase 3 on appliance |
| Production commissioning UI | 3 | **Rust Axum** + read-only JSON/HTML | Router appliance — no Python on edge |

Streamlit **starts** Rust binaries via subprocess. It does not replace them. Phase 1 Streamlit must not import BACnet crates or open serial ports directly except by launching the Rust CLI.

## Phase gates (do not skip)

| Phase | Gate | Evidence artifact |
|-------|------|-------------------|
| **1** | 10,000 alternating C+C exchanges @ 38,400, zero peer errors; unplug fault bounded | `captures/wire-test-38400.json` |
| **2** | Rescue gates 1–6: Clause 9 CRC; passive tokens 0+7; FEC RP AI:1173; mini-device; shared endpoint + mirror; soak — **no IP in device binary** | `captures/mstp-passive-*.json`, fec/mini reports |
| **3** | Routed B/IP → MS/TP; hop count; no broadcast loop; 8 h soak | Router telemetry + pcap |

Phase 1 **100-round smoke PASS** on bensbench (2026-08-28) is recorded in `docs/PHASE1_TEST_RESULTS.md` — not a substitute for the 10k gate.

**Phase 2 (2026-08-30):** pin `e3b9edb` (bbartling fork `vibe13-mstp` only). Gate 2 passive **PASS**. Gate 3 app + coexistence **PASS**. Gate 4 mini-device Workbench discover **PASS** (`device:123001`). Gates 5–6 **OPEN**. Do not mark soak/Gate 6 PASS without evidence.

## Repository map (what code does what)

```text
vibe_code_apps_13/
├── apps/serial-wire-test/     # Phase 1 Rust CLI — opens both FTDI ports, alternates framed bytes
├── apps/mstp-passive-sniff/   # Phase 2 RX-only decode (Gate 2)
├── apps/mstp-fec-diag/        # Phase 2 client-only FEC RP (Gate 3)
├── apps/mstp-mini-device/     # Phase 2 MS/TP device (Gate 4+)
├── apps/mstp-probe/           # Phase 2 acceptance / loopback
├── crates/lab-common/         # Shared envelope parser, JSON report, baud policy (no BACnet)
├── crates/mstp-lab/           # Thin rusty-bacnet boundary
├── tools/supervisory_console.py  # Phase 1 Streamlit lab UI
├── scripts/run_wire_dashboard.sh
├── captures/
└── docs/
```

## What Phase 1 proves (honest scope)

Phase 1 proves **physical RS-485 on real Waveshare C / FT232 hardware**:

- Two independent USB→UART→RS-485 transceiver paths on one Ubuntu tower
- A+/B-/REF wiring between adapters (daisy chain, not software loopback)
- Auto direction, 8N1, project baud rates (default 38,400)
- Bidirectional bytes with CRC — **private test envelope**, not BACnet MS/TP

It does **not** prove token passing, Who-Is, ReadProperty, or Metasys-style TRT until Phase 2.

## Supervisory metrics mapping

See [`SUPERVISORY_METRICS.md`](SUPERVISORY_METRICS.md). Streamlit **Live trunk** tab shows Phase 1 analogs of Metasys/Niagara/PXC diagnostics (good frames, CRC-ish errors, RTT, estimated bus load). Token TRT is ⚪ until Phase 2.

## Data contracts

See [`DATA_CONTRACT.md`](DATA_CONTRACT.md) for `wire-test-*.json` and `*-live.json` schemas.

## Agent commands (Phase 1)

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_13

# Lab UI (Streamlit)
./scripts/run_wire_dashboard.sh   # http://127.0.0.1:8765

# CLI (requires dialout + wired C+C adapters)
newgrp dialout   # or fresh login after usermod
cargo run --release -p serial-wire-test -- \
  --port-a /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BH002I9S-if00-port0 \
  --port-b /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BH001FQ0-if00-port0 \
  --baud 38400 --rounds 100 \
  --report captures/wire-test-smoke.json

# CI-safe (no hardware)
cargo test --workspace
./scripts/run_pty_smoke.sh 100 captures/wire-test-pty-ci.json
```

## PR / CI

- Workflow: `.github/workflows/vibe13-ci.yml` (fmt, clippy, unit tests, PTY smoke)
- Feature branch example: PR #126 `feat/vibe13-phase1-serial-wire-test`

## Agent rules (summary)

1. **Phase 1:** no BACnet in Rust or Python product paths.
2. **Streamlit:** lab only; subprocess to Rust; never ship Streamlit on the router image.
3. **Serial:** `/dev/serial/by-id/...`; user in `dialout`; one process per tty.
4. **Evidence:** commit passing JSON under `captures/wire-test-*.json`; do not claim Phase N+1 gates from Phase N artifacts.
5. **rusty-bacnet:** pin exact commit in `Cargo.lock` when Phase 2 starts; inspect source before coding APIs.
