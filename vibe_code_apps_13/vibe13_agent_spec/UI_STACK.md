# UI stack — Streamlit lab vs Rust appliance

## Canonical decision

**Yes — Streamlit for the lab now; Rust web for the appliance later.** That split matches how Metasys/Niagara/Siemens supervisory UIs work vs field tools: Python UI on the bench, Rust on the box.

## What you have now (Phase 1 lab)

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_13
./scripts/run_wire_dashboard.sh   # → http://127.0.0.1:8765
```

| Tab | What it does |
|-----|----------------|
| **Run control** | Set baud (9600–115200), FTDI by-id ports, Smoke 100 / Gate 10k → **Start** runs Rust `serial-wire-test`; **Stop** kills it |
| **Live trunk** | Supervisory-style health table (🟢🟡🔴), RTT sparkline, bus load estimate, auto-refresh |
| **Post-run** | Finished JSON reports + latency bars |
| **Roadmap** | Phase 1 vs 2 (`rusty-bacnet` MS/TP) vs 3 (Axum router UI) |

Implementation: `tools/supervisory_console.py`  
Launcher: `scripts/run_wire_dashboard.sh`  
Python deps: `requirements-wire-dashboard.txt` — installed into **`.venv`** by `run_wire_dashboard.sh` (not system pip on Ubuntu).

## Streamlit vs Rust web

| | **Streamlit (now)** | **Rust Axum web (Phase 3)** |
|--|---------------------|------------------------------|
| Where | bensbench lab | Router appliance |
| Role | Start tests, tune baud, watch commissioning | Production status / diagnostics |
| Stack | Python + subprocess → Rust binary | All Rust, no Python on edge |
| Operator analogy | Engineering laptop / temporary supervisory view | NAE/JACE/PXC-grade trunk diagnostics |

**Recommendation:** keep Streamlit for Phase 1–2 lab work; build the Metasys-grade UI in Rust when the router ships.

## To run the 10k gate from the UI

1. `newgrp dialout` (or new terminal after `sudo usermod -aG dialout $USER`)
2. Open console → **Run control** → preset **Gate 10,000** → **Start**
3. **Live trunk** tab — watch progress + health table (~10–15 min)

Use **Build release binary** once if `target/release/serial-wire-test` is missing.

## Phase 2 UI note

Streamlit may gain tabs for MS/TP acceptance (Who-Is, RP/RPM) by launching `mstp-probe` / reading MS/TP telemetry JSON — still lab-only. Real token TRT and MS/TP CRC counters come from `rusty-bacnet`, not the Phase 1 envelope.

## Phase 3 UI note

Per `docs/PHASE_3_ROUTER_WEB_APP.md`: read-only Axum endpoint first (structured logs + JSON), HTML dashboard only after router data-plane gate passes. Do not embed Streamlit in the product image.
