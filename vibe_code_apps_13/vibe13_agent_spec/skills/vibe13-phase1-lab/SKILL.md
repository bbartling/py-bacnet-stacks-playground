---
name: vibe13-phase1-lab
description: >-
  Run and extend Vibe13 Phase 1 RS-485 wire lab: Rust serial-wire-test,
  Streamlit supervisory console, captures JSON evidence. Use for checkpoint 13
  Phase 1 hardware, dashboard, or agent spec work.
---

# Vibe13 Phase 1 lab skill

Read first: `vibe13_agent_spec/SPEC.md`, `vibe13_agent_spec/UI_STACK.md`, root `AGENTS.md`.

## Launch Streamlit (lab UI)

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_13
./scripts/run_wire_dashboard.sh
# http://127.0.0.1:8765 — auto-creates .venv (Ubuntu blocks system pip)
```

## Hardware prerequisites

- Two Waveshare USB TO RS485 **(C)** / FT232, front USB, by-id paths in config
- A+↔A+, B-↔B-, GND/REF↔GND/REF (no 5V between adapters)
- User in `dialout`: `sudo usermod -aG dialout $USER` then new login or `newgrp dialout`

## Rust CLI (what Streamlit starts)

```bash
cargo run --release -p serial-wire-test -- \
  --port-a /dev/serial/by-id/... \
  --port-b /dev/serial/by-id/... \
  --baud 38400 --rounds 10000 \
  --report captures/wire-test-38400.json
```

Live progress: `captures/wire-test-38400-live.json` (auto, every 10 rounds).

## Scope guard

- Phase 1: **no** BACnet, MS/TP, token, UDP, or Axum in this phase's product code
- Streamlit: subprocess to Rust only; lab on bensbench, not on appliance image

## Evidence

Update `docs/PHASE1_TEST_RESULTS.md` after hardware gates. Commit `captures/wire-test-*.json` for passing runs.
