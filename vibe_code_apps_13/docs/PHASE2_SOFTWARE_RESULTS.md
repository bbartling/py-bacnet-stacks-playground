# Phase 2 — Software / pin results

**Date:** 2026-08-30  
**Branch:** `fix/vibe13-mstp-crc-phase2`  
**rusty-bacnet pin:** `bbartling/rusty-bacnet` @ `73a1fd41df7df2dfb3fa005cf339f347751f0286`  
(Upstream CRC PR: https://github.com/jscott3201/rusty-bacnet/pull/464 — still required.)  
**Follow-up (required before live TX):** Clause 9.5.6 token/PFM — https://github.com/jscott3201/rusty-bacnet/pull/465 (`e3b9edb` on `fix/mstp-clause956-token-pfm`).

**Hardware evidence:** Gate 2 passive **PASS**. Gate 3 **application exchange PASS / coexistence FAIL**. Active TX **blocked** until #465 + deterministic tests are pinned. Loopback ≠ hardware.

## Root-cause correction

| Claim | Verdict |
|-------|---------|
| Token `55 FF 00 00 07 00 00 37` has “invalid” header CRC | **Wrong** — Clause 9.6 `CRC8([00,00,07,00,00]) == 0x37` |
| Primary blocker was USB `latency_timer` | Partial — latency matters for delivery; **CRC polys** were the interoperability break |
| Prior rusty-bacnet CRC `0xE0` / `0xA001` | Incorrect (self-round-trip only) |
| Correct polys | Header `0x81`, data `0x8408` |
| USB read gaps as `T_frame_abort` | Incorrect host policy — fixed in `a9912b8` |
| Gate 3 FEC read success ⇒ trunk coexistence OK | **Wrong** — Workbench/FEC went offline while MAC 3 participated |
| Root cause of coexistence FAIL | Clause **9.5.6** master SM (reversed maintenance scan `PS=NS+1`, Token `TS→TS`) — **not** CRC/wiring/latency/APDU/Max_Master |

## Software checks (CRC pin `73a1fd4`)

| Check | Result |
|-------|--------|
| Upstream `cargo test -p bacnet-transport` (Clause 9 golden + stream) | PASS (2026-08-30) |
| Vibe13 offline Token 0←7 fixture (`mstp-passive-sniff` unit tests) | expected PASS after lock update |
| `./scripts/check_mstp_no_ip.sh` | required before handoff |
| Loopback `mstp-probe` | still valid software smoke; `hardware_evidence=false` |

## Software checks (9.5.6 PR #465 — not yet pinned in workspace)

| Check | Result |
|-------|--------|
| Regressions A–E (`clause956_tests.rs`) | PASS on `e3b9edb` |
| 2000-rotation ring `0→3→7→0`, no self-token | PASS |
| Live TX retest | **BLOCKED** until pin + token-edge telemetry |

## Phase 2 hardware gates (Rescue prompt)

| Gate | Status |
|------|--------|
| 1 Transport CRC + USB fragmentation | **PASS** on pin `73a1fd4` |
| 2 Passive live bus | **PASS** — `captures/mstp-passive-crc-fixed.json` |
| 3 Client FEC application exchange | **PASS** one-shot — `captures/mstp-fec-ai1173-oneshot.json` |
| 3 Network coexistence | **FAIL** — `captures/mstp-gate3-coexistence-abort.json` (Workbench/FEC offline under MAC 3 TX) |
| 3 Overall | **FAIL** / active TX blocked |
| 4 Mini-device server-only | **BLOCKED** |
| 5 Combined endpoint + mirror | **BLOCKED** |
| 6 Soak | **BLOCKED** — 20×30s must not be marked PASS |

### Gate 3 abort notes

- `application_exchange_ok=true`, `coexistence_ok=false`, `overall_ok=false`
- `exit_reason="aborted: existing MS/TP trunk went offline"`
- Invalid maintenance path at `TS=3,NS=7,Max_Master=7` previously set `PS=next(NS)=0` and PFM’d BASRT, allowing ring `0→3→0` and excluding FEC 7
- Waveshare C may also load the trunk electrically (fixed termination) — unplug before resuming open-fdd bosspi MQTT soaks if Workbench is offline

### Re-test order (after #465 pin only)

1. Passive 60s (Workbench online)  
2. Active join, **no** application traffic — verify token edges `0→3`, `3→7`, `7→0`  
3. One Who-Is  
4. One ReadProperty  
5. Five 30s reads while operator watches Workbench  
6. Only then twenty-read soak  

A successful FEC read alone must never set `hardware_ok=true`.

## Known limitations

- Workspace still on CRC tip `73a1fd4` until #465 is reviewed and re-pinned.
- Shared server+requester endpoint (Workstream E) not implemented yet.
- Transitive `socket2` still present; runtime must not open IP sockets (Phase 2 apps).
- PR #126 is merged on `develop` (`eb178f70`); old USB-only Cursor plan is historical.
