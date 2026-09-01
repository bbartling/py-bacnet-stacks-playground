# Phase 2 — Prototype closeout (historical checkpoint)

**Closed:** 2026-08-31  
**Vibe13 project SHA:** `26b71d02575f978d22a9d6eb24423dfe74274fb2` (`develop` after PR #127)  
**rusty-bacnet pin (frozen):** `jscott3201/rusty-bacnet` @ `af4e88680c51eb4da64dac47f0540a35bf184732`  
**Do not repin** merely because upstream `dev` has moved. Router/appliance work belongs in a separate repository.

## What this checkpoint is

A **stable, historical lab prototype**: server-only, standard-frame BACnet MS/TP mini-device at **38,400 baud** on the tested BASRT (MAC 0) + JCI FEC (MAC 7) + Waveshare USB TO RS485 (C) topology. Not a router, not conformance-certified, not an active product line.

## Evidence closed on pin `af4e886`

| Gate | Result | Artifact |
|------|--------|----------|
| 1 — wire / lab-common | PASS (historical) | `captures/wire-test-*.json` |
| 2 — passive sniff | PASS | `captures/mstp-passive-af4e886-60s.json` |
| 3 — FEC client RP | PASS | `captures/mstp-fec-ai1173-af4e886-oneshot.json` |
| 4 — mini-device server | PASS | Workbench `device:123001`; `captures/mstp-mini-device-af4e886.log` |
| 4b — Haystack trunk | PASS | `captures/haystack-trunk/` |
| 5–6 — shared endpoint / mirror | **OUT OF SCOPE** | not attempted |
| 1h hardware soak | run [`scripts/run_mstp_mini_soak.sh`](../scripts/run_mstp_mini_soak.sh) | see `captures/mstp-soak-af4e886-*` |
| 24h continuity (same PID) | **PASS** | [`captures/mini-device-24h-continuity-20260901T200935Z.txt`](../captures/mini-device-24h-continuity-20260901T200935Z.txt) |
| USB unplug gate | **DEFERRED** | [`scripts/run_mstp_usb_unplug_gate.sh`](../scripts/run_mstp_usb_unplug_gate.sh) |
| Linux timing baseline | **PASS** | [`captures/linux-timing-af4e886-20260901T201201Z/`](../captures/linux-timing-af4e886-20260901T201201Z/) |

Full manifest: [`PHASE2_HARDWARE_EVIDENCE.md`](PHASE2_HARDWARE_EVIDENCE.md).

**Haystack** validates trunk online (`check` / `fec-only`) and offline-with-FEC-ok (`mini-offline`) during soak and unplug gates.

Captures labeled `19d205d`, `e3b9edb`, `6a70b85`, or `bbartling` fork are **historical** — not evidence for `af4e886`.

## Offline contract (closeout session)

Run from `vibe_code_apps_13/`:

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace --locked
./scripts/check_mstp_no_ip.sh
./scripts/check_mstp_no_ip_runtime.sh
```

Record results in [`PHASE2_SOFTWARE_RESULTS.md`](PHASE2_SOFTWARE_RESULTS.md).

## Explicitly out of scope (do not add to Vibe13)

- shared client+server MS/TP endpoint;
- FEC point mirror;
- B/IP-to-MS/TP router, BBMD/FDR, Buildroot image, dashboard;
- extended MS/TP frames or conformance claims;
- continual chase of moving upstream `dev`.

## Allowed claim

> Vibe13 provides a stable, server-only, standard-frame BACnet MS/TP lab device at 38,400 baud on the tested BASRT/FEC/Waveshare topology.

## Not allowed

Clause 9 conformant, BTL, extended MS/TP, segmentation, FEC mirror, router, or USB-unplug hardware gate claims.
