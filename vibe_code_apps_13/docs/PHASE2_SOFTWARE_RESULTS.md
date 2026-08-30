# Phase 2 — Software / pin results

**Date:** 2026-08-30  
**Branch:** `fix/vibe13-mstp-crc-phase2`  
**rusty-bacnet pin:** `bbartling/rusty-bacnet` @ `73a1fd41df7df2dfb3fa005cf339f347751f0286`  
(Upstream PR: https://github.com/jscott3201/rusty-bacnet/pull/464 — re-pin to `jscott3201` when merged.)

**Hardware evidence:** Gate 2 passive **PASS** (`captures/mstp-passive-crc-fixed.json`). Gate 3+ OPEN. Loopback ≠ hardware.

## Root-cause correction

| Claim | Verdict |
|-------|---------|
| Token `55 FF 00 00 07 00 00 37` has “invalid” header CRC | **Wrong** — Clause 9.6 `CRC8([00,00,07,00,00]) == 0x37` |
| Primary blocker was USB `latency_timer` | Partial — latency matters for delivery; **CRC polys** were the interoperability break |
| Prior rusty-bacnet CRC `0xE0` / `0xA001` | Incorrect (self-round-trip only) |
| Correct polys | Header `0x81`, data `0x8408` |
| USB read gaps as `T_frame_abort` | Incorrect host policy — fixed in `a9912b8` |

## Software checks (this pin)

| Check | Result |
|-------|--------|
| Upstream `cargo test -p bacnet-transport` (Clause 9 golden + stream) | PASS (2026-08-30) |
| Vibe13 offline Token 0←7 fixture (`mstp-passive-sniff` unit tests) | expected PASS after lock update |
| `./scripts/check_mstp_no_ip.sh` | required before handoff |
| Loopback `mstp-probe` | still valid software smoke; `hardware_evidence=false` |

## Phase 2 hardware gates (Rescue prompt)

| Gate | Status |
|------|--------|
| 1 Transport CRC + USB fragmentation | **Software PASS** on pin `73a1fd4` |
| 2 Passive live bus | **PASS** 2026-08-30 — `captures/mstp-passive-crc-fixed.json` (45s: rx=25651, frames=2971, tokens=2117, token_0_from_7=1058, sources=[0,7], invalid=2, valid_ratio≈0.999) |
| 3 Client-only FEC AI:1173 | **PASS one-shot** — `captures/mstp-fec-ai1173-oneshot.json` (I-Am@7, `BENS BENCHTEST BOX`, PV≈75.57). 20×30s: `captures/mstp-fec-ai1173-30s.*`. Rust `--max-master 7` for PFM join. |
| 4 Mini-device server-only | **OPEN** |
| 5 Combined endpoint + mirror | **OPEN** (needs Workstream E upstream) |
| 6 Soak | **OPEN** |

### Gate 2 notes

- `latency_timer` was **16** during the PASS (not 1). Optional: `echo 1 | sudo tee /sys/bus/usb-serial/devices/ttyUSB0/latency_timer`
- Workbench observation: operator should confirm still online (agent did not kill trunk).
- No Rust TX (passive sniff only).

## Known limitations

- Pin is on **bbartling fork** until upstream #464 merges.
- Shared server+requester endpoint (Workstream E) not implemented yet.
- Transitive `socket2` still present; runtime must not open IP sockets (Phase 2 apps).
- PR #126 is merged on `develop` (`eb178f70`); old USB-only Cursor plan is historical.
