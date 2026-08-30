# Phase 2 — Software / pin results

**Date:** 2026-08-30  
**Branch:** `fix/vibe13-mstp-crc-phase2`  
**rusty-bacnet pin:** `bbartling/rusty-bacnet` @ `19d205d78c947aea3fe98110d8a6c392359aa627` (rebased on upstream `dev`; MS/TP equivalent to lab pin `e3b9edb`)  
**Upstream PR:** https://github.com/jscott3201/rusty-bacnet/pull/467

**Hardware evidence:** Gate 2 passive **PASS**. Gate 3 FEC application **PASS**. Gate 3 coexistence **PASS** on `e3b9edb` (mini-device MAC 3 + Workbench/FEC stay up). Gate 4 mini-device **PASS** (JENEsys discover + points `{ok}`). Gates 5–6 still open. Loopback ≠ hardware for soak claims.

## Status model (explicit)

| Gate | Software / offline | Live hardware |
|------|-------------------|---------------|
| 1 CRC + USB stream | **PASS** | **PASS** (via pin) |
| 2 Passive | n/a | **PASS** `mstp-passive-crc-fixed.json` |
| 3 FEC client app exchange | loopback N/A | **PASS** oneshot |
| 3 Network coexistence | regressions A–E **PASS** | **PASS** on `e3b9edb` (Workbench online with MAC 3 TX) |
| 4 Mini-device discoverable | loopback acceptance **PASS** | **PASS** JENEsys device:123001 + 4 points Polled `{ok}` |
| 5 Shared endpoint + mirror | **OPEN** | **OPEN** |
| 6 Long soak | **OPEN** | **OPEN** |

## Root-cause correction

| Claim | Verdict |
|-------|---------|
| Token header CRC “invalid” | **Wrong** — Clause 9.6 polys |
| Primary blocker = `latency_timer` | Partial; CRC was the decode break |
| Gate 3 FEC read ⇒ coexistence OK | **Wrong** on `73a1fd4` — FAIL until 9.5.6 |
| Coexistence root cause | Clause **9.5.6** DONE_WITH_TOKEN / PFM (not Max_Master waits) |
| Fix location | Fork `vibe13-mstp` @ `e3b9edb` |

## Software checks (pin `e3b9edb`)

| Check | Result |
|-------|--------|
| `cargo test -p bacnet-transport --lib` (incl. clause956 A–E) | PASS |
| Workspace pin + `Cargo.lock` → `e3b9edb` | PASS |
| `./scripts/check_mstp_no_ip.sh` | OK local sources; socket2 transitive **documented BLOCKED** in `captures/phase2-no-ip-gate-status.txt` |
| Loopback `mstp-probe` / acceptance | PASS (`hardware_evidence=false`) |
| `TokenEdgeCounters` unit tests | PASS |

## Gate 4 Workbench notes (2026-08-30)

- Device **Rust MS/TP Mini Device** / `device:123001` / MAC **3** discovered; `systemStatus=Operational`.
- Points: AI:1, BI:1, AV:2, BV:2 all **Polled `{ok}`**.
- Niagara may show Write=`readonly` on AV/BV after discover-add — that is often a **Niagara point facet**, not proof the BACnet objects reject WP. Validate with an explicit WriteProperty / priority command.
- AI units are BACnet **degrees-Fahrenheit (62)**; Niagara UI may display `°C` depending on facets.
- Name slash may become `Rust MS.TP…` in Niagara — cosmetic.

## Active-TX / open-fdd note

Do **not** resume open-fdd bosspi MQTT soaks on this Waveshare while mini-device owns the tty. Unplug Waveshare (or stop mini-device) before bosspi fieldbus, and keep pin ≥ `e3b9edb` if rejoining this trunk.

## Known limitations

- Gates 5–6 not claimed (shared endpoint + soak).
- Transitive `socket2` still in dep graph; runtime must not open IP sockets.
- Not a Clause 9 conformance claim; no extended frames (32/33 / COBS / CRC-32K).
- Host USB stale-partial timeout ≠ wire `T_frame_abort`.
- Upstream contribution is open as PR #467 (MS/TP-only; Windows retry-budget timeout stays on fork `main` only).
