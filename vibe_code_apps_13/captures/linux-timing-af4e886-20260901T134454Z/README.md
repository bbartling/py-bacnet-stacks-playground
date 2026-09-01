# Linux timing gate — `af4e886` (2026-09-01)

**Verdict:** **PARTIAL** (see [`ERRATA.md`](ERRATA.md))  
**Artifact window:** 2026-09-01T13:44:54Z → 2026-09-01T14:09:57Z (~25 min)  
**rusty-bacnet pin:** `af4e88680c51eb4da64dac47f0540a35bf184732`  
**Mini-device PID:** 646770 (unchanged; ~22.3h elapsed at start; retrospective 24h+ **N** at capture time)  
**cyclictest mode:** privileged Docker (`--pid=host`) fallback — host lacks `RTPRIO`/`cap_sys_nice`

## Cyclictest vs 60 bit times @ 38400 baud (1.5625 ms scheduling-risk indicator only)

| Phase | Duration | Min (µs) | Avg (µs) | Max (µs) | Status |
|-------|----------|----------|----------|----------|--------|
| Idle | 600 s | 4 | 5 | 365 | reference |
| Loaded (`stress-ng`) | 900 s | 4 | 5 | 197 | **INVALID** — stress-ng failed |

**stress-ng:** failed (`libIPSec_MB.so.1` missing). Loaded cyclictest ran without verified load.

## Trunk health

- Haystack before/after: **not captured** in this directory (README overclaimed)
- No FTDI/USB disconnect/reset in `kernel-usb-*.txt`
- MS/TP counter deltas: N/A (mini-device does not export CRC counters)

## Kernel

- `6.8.0-138-generic` PREEMPT_DYNAMIC, `CONFIG_HZ=1000`, `CONFIG_HIGH_RES_TIMERS=y`
- FTDI `latency_timer`: 16
