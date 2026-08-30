# Vibe13 agent workspace — orientation

Plain Markdown in **`vibe13_agent_spec/`** is the source of truth for AI agents working on checkpoint 13. Product code and Rust workspace live in **`vibe_code_apps_13/`** parent directory.

**Primary engineering contract:** [`../AGENTS.md`](../AGENTS.md)  
**Full spec:** [`SPEC.md`](SPEC.md)  
**UI stack (Streamlit vs Rust):** [`UI_STACK.md`](UI_STACK.md)  
**Supervisory metrics:** [`SUPERVISORY_METRICS.md`](SUPERVISORY_METRICS.md)  
**JSON contracts:** [`DATA_CONTRACT.md`](DATA_CONTRACT.md)

## Current phase (2026-08-30)

| Item | Value |
|------|--------|
| Baseline | `develop` @ `eb178f70` (PR #126 merged) |
| Active work | **Phase 2 Rescue** — Clause 9 CRC + USB stream → passive → FEC client → mini-device → shared endpoint → FEC OA-T mirror |
| rusty-bacnet pin | `bbartling/rusty-bacnet` @ `73a1fd4…` (upstream [#464](https://github.com/jscott3201/rusty-bacnet/pull/464)) |
| Bench | BASRT MAC0 + FEC MAC7 + Waveshare C; Rust MAC **3**; baud 38400; Max_Master 127 |
| Historical | Cursor plan `vibe13_ms_tp_usb_fix_*` is **not** active |

**Do not invent hardware PASS.** Gate evidence lives under `captures/` + `docs/PHASE2_SOFTWARE_RESULTS.md` + `docs/PHASE2_HARDWARE_RUNBOOK.md`.

## Quick start (Phase 1 lab UI)

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_13
./scripts/run_wire_dashboard.sh
```

Requires: `dialout` for hardware; Waveshare **C** on the live trunk. Dashboard uses `./scripts/run_wire_dashboard.sh` (auto-creates `.venv` — do not `pip install` system-wide on Ubuntu PEP 668).

## Quick start (Phase 2 passive — no TX)

```bash
PORT=/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BH001FQ0-if00-port0
cargo run --release -p mstp-passive-sniff -- \
  --serial "$PORT" --baud 38400 --seconds 60 \
  --report captures/mstp-passive-crc-fixed.json
```

## Agent rules (additions to root AGENTS.md)

1. **Document UI split:** Streamlit = lab; Rust Axum = Phase 3 appliance. Never plan Python on the router image.
2. **Phase 1 honesty:** private envelope proves RS-485 transceivers — not BACnet MS/TP.
3. **Subprocess boundary:** Streamlit launches `target/release/serial-wire-test`; do not reimplement serial I/O in Python.
4. **Evidence paths:** `captures/wire-test-*.json` for gates; update `docs/PHASE1_TEST_RESULTS.md` after hardware runs.
5. **Phase 2 entry:** read `docs/PHASE_2_MSTP_MINI_DEVICE.md`, pin `rusty-bacnet`, no B/IP in device binary.
6. **CRC truth:** Token `… 37` is **valid**; wrong polys were the blocker (D-011).
7. **One tty owner:** never two `MstpTransport`s / BACnetServer+Client opening the same port.
8. **MAC policy:** never TX as 0 with BASRT present; never use FEC’s 7; use 3 after confirming free.

## Index

| Doc | Topic |
|-----|-------|
| [SPEC.md](SPEC.md) | Mission, phases, repo map, gates |
| [UI_STACK.md](UI_STACK.md) | Streamlit console tabs, Rust web later |
| [SUPERVISORY_METRICS.md](SUPERVISORY_METRICS.md) | Metasys/Niagara mapping |
| [DATA_CONTRACT.md](DATA_CONTRACT.md) | Report / live JSON schemas |
| [../docs/PHASE1_CHEATSHEET.md](../docs/PHASE1_CHEATSHEET.md) | Wiring + CLI |
| [../docs/PHASE1_TEST_RESULTS.md](../docs/PHASE1_TEST_RESULTS.md) | Pass/fail log |
| [../docs/PHASE2_HARDWARE_RUNBOOK.md](../docs/PHASE2_HARDWARE_RUNBOOK.md) | Live BASRT/FEC commands |
| [../docs/PHASE2_SOFTWARE_RESULTS.md](../docs/PHASE2_SOFTWARE_RESULTS.md) | Pin + gate status |
| [../docs/DECISIONS.md](../docs/DECISIONS.md) | D-001…D-012 |
