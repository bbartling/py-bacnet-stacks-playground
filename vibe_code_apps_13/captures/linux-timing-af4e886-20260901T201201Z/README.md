# Linux timing gate — `af4e886` (2026-09-01, post-fix)

**Verdict:** PASS  
**Artifact window:** 2026-09-01T20:12:01Z → 2026-09-01T20:37:26Z (~25 min)  
**rusty-bacnet pin:** `af4e88680c51eb4da64dac47f0540a35bf184732`  
**Mini-device PID:** 646770 (unchanged; ~28.8h elapsed at start; retrospective 24h+ **Y**)  
**cyclictest mode:** privileged Docker (`--pid=host`) fallback — 1 thread reported despite `-m` SMP  
**stress-ng mode:** Docker (`ubuntu:24.04`) — exit code 0

## Cyclictest vs 60 bit times @ 38400 baud (1.5625 ms scheduling-risk indicator only)

| Phase | Duration | Threads | Min (µs) | Avg (µs) | Max (µs) |
|-------|----------|---------|----------|----------|----------|
| Idle | 600 s | 1 | 4 | 5 | 239 |
| Loaded (`stress-ng`) | 900 s | 1 | 4 | 11 | 2639 |

**stress-ng:** Docker fallback; `stress-ng.exit` = 0. Loaded max 2639 µs still below multiple bit-times but higher than idle — expected under load.

**Clause 9:** Scheduling latency below 1,562.5 µs is a **host-risk** measurement only — not wire-timing conformance.

## Trunk health

- Haystack `check` PASS before and after gate (`haystack-before/`, `haystack-after/`)
- No FTDI/USB disconnect/reset in `kernel-usb-*.txt`
- MS/TP counter deltas: N/A (mini-device does not export CRC counters)

## Kernel / RT

- `6.8.0-138-generic` PREEMPT_VOLUNTARY + PREEMPT_DYNAMIC, `CONFIG_HZ=1000`, `CONFIG_HIGH_RES_TIMERS=y`
- cyclictest `SCHED_FIFO` priority 80 (`P:80` on T: lines)
- Container digest: `ubuntu@sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517`

## Prior capture

[`../linux-timing-af4e886-20260901T134454Z/`](../linux-timing-af4e886-20260901T134454Z/) — **PARTIAL** (loaded invalid); see `ERRATA.md`.
