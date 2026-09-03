# Phase 2 — Software results

**Updated:** 2026-09-01 (Linux timing evidence closeout)  
**rusty-bacnet pin (frozen):** `jscott3201/rusty-bacnet` @ `af4e88680c51eb4da64dac47f0540a35bf184732`  
**Upstream merged:** [#467](https://github.com/jscott3201/rusty-bacnet/pull/467) (CRC/token), [#468](https://github.com/jscott3201/rusty-bacnet/pull/468) (Python MS/TP surfaces)  
**Closeout docs:** [`PHASE2_PROTOTYPE_CLOSEOUT.md`](PHASE2_PROTOTYPE_CLOSEOUT.md), [`PHASE2_HARDWARE_EVIDENCE.md`](PHASE2_HARDWARE_EVIDENCE.md)

Historical captures with `19d205d` / `e3b9edb` / `bbartling` fork are **not** evidence for the current pin until revalidated.

## Classification (2026-08-31 audit)

| Class | Items |
|-------|--------|
| **Implemented/proven** | Clause 9 CRC + USB reassembly + token/PFM (#467); Python binding example (#468); Gate 1–4 on historical pin; loopback + CI acceptance on `af4e886` |
| **Current mini-device blocker** | Upstream transport health notification (app uses serial-path watchdog); simulation still remove/re-add AI/BI (needs `ObjectDatabase` in-place mutation API) |
| **Phase 2.1 mirror blocker** | Shared MS/TP endpoint (one tty, client+server) |
| **Phase 3 router blocker** | Extended frames 32/33, COBS, CRC-32K, B/IP↔MS/TP routing |
| **Conformance evidence gaps** | Six-baud timing matrix; golden vectors; BFR-derived router tests only in research doc |

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
| 1h soak script | **NOT RUN** — scripts ready | [`scripts/run_mstp_mini_soak.sh`](../scripts/run_mstp_mini_soak.sh) |
| 24h continuity (same PID) | **PASS** — process continuity + discoverability only (not instrumented CRC/token soak) — PID 646770, etimes>86400 at 2026-09-01T20:09:35Z | [`captures/mini-device-24h-continuity-20260901T200935Z.txt`](../captures/mini-device-24h-continuity-20260901T200935Z.txt) |
| USB unplug gate | **DEFERRED** — operator gate | [`scripts/run_mstp_usb_unplug_gate.sh`](../scripts/run_mstp_usb_unplug_gate.sh) |
| Linux timing baseline | **measurement_complete** — host scheduler only; loaded max **exceeded** 1562.5 µs indicator | [`captures/linux-timing-af4e886-20260901T201201Z/`](../captures/linux-timing-af4e886-20260901T201201Z/) |
| On-wire Clause 9 timing | **DEFERRED** — needs high-Z analyzer; not cyclictest | see capture `ASSESSMENT.md` |

### Linux cyclictest summary (2026-09-01 capture; semantics corrected 2026-09-03)

cyclictest measures **host scheduler latency**, not Clause 9 wire turnaround. Comparison value **1,562.5 µs** (60 bit times @ 38400 baud) is an **informational host-risk indicator only** — not a universal response deadline and **not** `T_frame_abort` conformance. cyclictest `-m` = **mlockall** (capture used **1 worker**).

| Phase | Duration | Min (µs) | Avg (µs) | Max (µs) | vs 1562.5 µs |
|-------|----------|----------|----------|----------|--------------|
| Idle | 600 s | 4 | 5 | 239 | **under** |
| Loaded (`stress-ng`, docker) | 900 s | 4 | 11 | **2639** | **exceeded** |

| Assessment | Value |
|------------|-------|
| measurement_execution | pass |
| stress_ng_execution | pass |
| haystack_before / after | pass |
| scheduling_threshold_assessment | **exceeded** |
| wire_timing_measured | false |
| clause9_conformance | not_claimed |

Prior capture **PARTIAL** (loaded invalid — stress-ng failure + gate bug): [`captures/linux-timing-af4e886-20260901T134454Z/`](../captures/linux-timing-af4e886-20260901T134454Z/) — see `ERRATA.md`.

## Haystack trunk revalidation (2026-08-31 session)

With mini-device running on trunk @ 38400:

| Mode | Result |
|------|--------|
| `fec-only` | PASS |
| `check` (FEC + Rust read-only-ai + device) | PASS |

Use `HAYSTACK_INSECURE=1` (or `HAYSTACK_CACERT`) with `~/open-fdd/.env` on the bench.

**Go/no-go:** **GO** for Gates 2–4+4b and mini-device process continuity. Linux timing = **host-risk characterization complete** with loaded indicator **exceeded** — **not** wire timing PASS. **No-go** for USB unplug, on-wire Clause 9 qualification, or conformance claims until analyzer runbook in [`PHASE2_HARDWARE_RUNBOOK.md`](PHASE2_HARDWARE_RUNBOOK.md) is satisfied.
