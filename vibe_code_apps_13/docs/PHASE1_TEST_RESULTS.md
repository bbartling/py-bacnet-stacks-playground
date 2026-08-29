# Phase 1 test results

## Software (no USB)

| Check | Result | When |
|-------|--------|------|
| `cargo test --workspace` | PASS (15 lab-common tests) | 2026-08-28 |
| `cargo clippy --workspace --all-targets -- -D warnings` | PASS | 2026-08-28 |
| PTY null-modem smoke (`scripts/run_pty_smoke.sh`, 50 rounds) | **PASS** | 2026-08-28 — `captures/wire-test-pty-smoke.json` |

PTY smoke proves the coordinator/parser/report path. It is **not** a hardware Phase 1 gate.

## Hardware inventory (bensbench, 2026-08-28)

Both **Waveshare USB TO RS485 (C)** / FT232R enumerated on front USB:

| Label | USB serial | by-id | Current tty |
|-------|------------|-------|-------------|
| A (tape TBD) | `BH002I9S` | `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BH002I9S-if00-port0` | `ttyUSB0` |
| B (tape TBD) | `BH001FQ0` | `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BH001FQ0-if00-port0` | `ttyUSB1` |

Map physical A/B by unplug: yank one stick, see which by-id vanishes, apply tape.

### Host blockers before C+C hardware gate

1. `ben` is **not** in `dialout` — ports are `root:dialout` mode `660`.
   ```bash
   sudo usermod -aG dialout "$USER"
   # then log out/in (or new session); verify: id | grep dialout
   ```
2. RS-485 A+/B-/GND/REF must be wired between the two C adapters (no 5V).
3. Prefer by-id paths in the CLI, never hard-code `ttyUSB0/1`.

### Hardware suite (after dialout + wire)

| Check | Result | Report |
|-------|--------|--------|
| 100-round @ 38400 C+C | **PASS** (100/100, 0 peer errors) | `captures/wire-test-smoke.json` — bensbench 2026-08-28 |
| 10 000-round @ 38400 C+C | pending | `captures/wire-test-38400.json` |
| Unplug B mid-run | pending | failed JSON, nonzero exit |
| FTDI `latency_timer` | pending | record 1 ms if set |

Phase 1 **hardware** pass requires zero missing/corrupt/duplicate **peer** frames on the 10k run.
