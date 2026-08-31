# Phase 2 — Software results

**Updated:** 2026-08-31 (hardware evidence closeout in progress)  
**rusty-bacnet pin (frozen):** `jscott3201/rusty-bacnet` @ `af4e88680c51eb4da64dac47f0540a35bf184732`  
**Upstream merged:** [#467](https://github.com/jscott3201/rusty-bacnet/pull/467) (CRC/token), [#468](https://github.com/jscott3201/rusty-bacnet/pull/468) (Python MS/TP surfaces)  
**Vibe13 project SHA:** `8e0b35429d17be852057bef0907c9f571f2a9e32` (`develop` after PR #128)  
**Closeout docs:** [`PHASE2_PROTOTYPE_CLOSEOUT.md`](PHASE2_PROTOTYPE_CLOSEOUT.md), [`PHASE2_HARDWARE_EVIDENCE.md`](PHASE2_HARDWARE_EVIDENCE.md)

Historical captures with `19d205d` / `e3b9edb` / `bbartling` fork are **not** evidence for the current pin until revalidated.

## Classification (2026-08-31 audit)

| Class | Items |
|-------|--------|
| **Implemented/proven** | Clause 9 CRC + USB reassembly + token/PFM (#467); Python binding example (#468); Gate 1–4 on historical pin; loopback + CI acceptance on `af4e886` |
| **Current mini-device blocker** | Upstream transport health notification (app uses serial-path watchdog); simulation still remove/re-add AI/BI (needs `ObjectDatabase` in-place mutation API) |
| **Phase 2.1 mirror blocker** | Shared MS/TP endpoint (one tty, client+server) |
| **Phase 3 router blocker** | Extended frames 32/33, COBS, CRC-32K, B/IP↔MS/TP routing |
| **Conformance evidence gaps** | Six-baud timing matrix; golden vectors; 24h soak; BFR-derived router tests only in research doc |

## Upstream candidate PRs (local branches in `~/src/rusty-bacnet`)

| Branch | Topic |
|--------|--------|
| `fix/mstp-validate-rust-config` | Rust `MstpConfig` validation parity with Python |
| `fix/mstp-tx-completion-after-drain` | `tcdrain` after serial write + wire-delay regression |

## Software checks (`af4e886`)

| Check | Result |
|-------|--------|
| `cargo fmt --all -- --check` | PASS |
| `cargo clippy --workspace --all-targets -- -D warnings` | PASS |
| `cargo test --workspace --locked` | PASS |
| `./scripts/check_mstp_no_ip.sh` | PASS (transitive `socket2` documented) |
| `./scripts/check_mstp_no_ip_runtime.sh` | PASS (no AF_INET on PTY startup) |
| `mstp-probe --profile smoke loopback` | PASS |

## Transport / timing limitations (honest)

- `TokioSerialPort::write` on pin `af4e886` completes after `write_all` only — **no `tcdrain`**. Upstream fix proposed on branch `fix/mstp-tx-completion-after-drain`.
- Mini-device exits when serial by-id path disappears (USB unplug watchdog); does not yet observe MS/TP recv-task exit via public server API.

## Allowed acceptance language (after post-pin hardware + Haystack Gate 4b)

> Vibe13 provides a stable, server-only, standard-frame BACnet MS/TP lab device at 38,400 baud on the tested BASRT/FEC/Waveshare topology.

## Hardware revalidation (`af4e886`, 2026-08-31)

| Step | Result | Artifact |
|------|--------|----------|
| Passive sniff 60s @ 38400 | PASS (tokens 2835, MAC 0+7, no TX) | `captures/mstp-passive-af4e886-60s.json` |
| Gate 3 FEC AI:1173 one-shot | PASS | `captures/mstp-fec-ai1173-af4e886-oneshot.json` |
| Haystack Gate 4b (after ~2 min settle) | PASS | `captures/haystack-trunk/` |
| Mini-device MAC 3 @ 38400 | PASS (read-only-ai ok) | `captures/mstp-mini-device-af4e886.log` |
| 1h / 24h soak | **NOT RUN** — scripts ready | [`scripts/run_mstp_mini_soak.sh`](../scripts/run_mstp_mini_soak.sh) |
| USB unplug gate | **NOT RUN** — scripts ready | [`scripts/run_mstp_usb_unplug_gate.sh`](../scripts/run_mstp_usb_unplug_gate.sh) |
| Linux timing baseline | **PARTIAL** (kernel+FTDI; cyclictest skip — install `rt-tests`) | [`captures/linux-timing-af4e886-20260831T180531Z/`](../captures/linux-timing-af4e886-20260831T180531Z/) |

## Haystack trunk revalidation (2026-08-31 session)

With mini-device running on trunk @ 38400:

| Mode | Result |
|------|--------|
| `fec-only` | PASS |
| `check` (FEC + Rust read-only-ai + device) | PASS |

Use `HAYSTACK_INSECURE=1` (or `HAYSTACK_CACERT`) with `~/open-fdd/.env` on the bench.

**Go/no-go:** **GO** for Gates 2–4+4b and continued lab use. **No-go** for 1h/24h soak, unplug hardware gate, or conformance claims until operator runs the scripts in [`PHASE2_HARDWARE_RUNBOOK.md`](PHASE2_HARDWARE_RUNBOOK.md).
