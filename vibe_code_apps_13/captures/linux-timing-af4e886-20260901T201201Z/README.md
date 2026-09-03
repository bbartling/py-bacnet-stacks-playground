# Linux timing gate — `af4e886` (2026-09-01 capture; semantics corrected 2026-09-03)

**Gate result label:** `measurement_complete` (not Clause 9 PASS)  
**Artifact window:** 2026-09-01T20:12:01Z → 2026-09-01T20:37:26Z (~25 min)  
**rusty-bacnet pin:** `af4e88680c51eb4da64dac47f0540a35bf184732` (frozen — unchanged)  
**Mini-device PID:** 646770 (unchanged; ~28.8h elapsed at start; retrospective 24h+ continuity **Y**)  
**cyclictest mode:** privileged Docker (`--pid=host`) fallback — **1 worker** reported; `-m` means **mlockall**, not one worker per CPU  
**stress-ng mode:** Docker (`ubuntu:24.04`) — exit code 0  
**git_dirty at capture:** `true` (preserved historical fact)

## Assessments (corrected)

| Field | Value |
|-------|-------|
| measurement_execution | **pass** |
| stress_ng_execution | **pass** |
| haystack_before / after | **pass** |
| scheduling_threshold_assessment (idle max 239 µs) | **under** 1562.5 µs |
| scheduling_threshold_assessment (loaded max **2639** µs) | **exceeded** 1562.5 µs |
| wire_timing_measured | **false** |
| clause9_conformance | **not_claimed** |

Raw `cyclictest-*.txt` / histograms are **unchanged**. See [`ASSESSMENT.md`](ASSESSMENT.md).

## Cyclictest vs 60 bit times @ 38400 baud (1.5625 ms host-risk indicator only)

| Phase | Duration | Threads | Min (µs) | Avg (µs) | Max (µs) | vs 1562.5 µs |
|-------|----------|---------|----------|----------|----------|--------------|
| Idle | 600 s | 1 | 4 | 5 | 239 | **under** |
| Loaded (`stress-ng`) | 900 s | 1 | 4 | 11 | **2639** | **exceeded** |

**stress-ng:** Docker fallback; `stress-ng.exit` = 0. Loaded max **2639 µs > 1562.5 µs** — host scheduling-risk indicator **exceeded** under load. This is **not** Clause 9 wire turnaround and **not** a T_frame_abort miss.

**Clause 9 / on-wire:** **not measured** in this capture. Deferred pending high-impedance differential / logic-analyzer qualification (do not substitute another cyclictest run).

## Trunk health

- Haystack `check` PASS before and after gate (`haystack-before/`, `haystack-after/`)
- No FTDI/USB disconnect/reset in `kernel-usb-*.txt`
- MS/TP counter deltas: N/A (mini-device does not export CRC counters)

## 24h continuity (related, separate artifact)

[`../mini-device-24h-continuity-20260901T200935Z.txt`](../mini-device-24h-continuity-20260901T200935Z.txt) proves **process continuity** and periodic discoverability (same PID, etimes>86400). It does **not** prove a fully instrumented protocol soak with CRC/token counter deltas.

## Kernel / RT

- `6.8.0-138-generic` PREEMPT_VOLUNTARY + PREEMPT_DYNAMIC, `CONFIG_HZ=1000`, `CONFIG_HIGH_RES_TIMERS=y`
- cyclictest `SCHED_FIFO` priority 80 (`P:80` on T: lines)
- Container digest: `ubuntu@sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517`

## Prior capture

[`../linux-timing-af4e886-20260901T134454Z/`](../linux-timing-af4e886-20260901T134454Z/) — **PARTIAL** (loaded invalid); see `ERRATA.md`.
