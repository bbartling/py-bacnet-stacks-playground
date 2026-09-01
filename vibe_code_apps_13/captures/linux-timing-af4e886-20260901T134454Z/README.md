# Linux timing gate — `af4e886` (2026-09-01)

**Verdict:** PASS  
**Artifact window:** 2026-09-01T13:44:54Z → 2026-09-01T14:09:57Z (~25 min)  
**rusty-bacnet pin:** `af4e88680c51eb4da64dac47f0540a35bf184732`  
**Mini-device PID:** 646770 (unchanged; ~22.3h elapsed at start; retrospective 24h+ **N**)  
**cyclictest mode:** privileged Docker (`--pid=host`) fallback — host lacks `RTPRIO`/`cap_sys_nice`

## Cyclictest vs 60 bit times @ 38400 baud (1.5625 ms scheduling-risk indicator only)

| Phase | Duration | Min (µs) | Avg (µs) | Max (µs) |
|-------|----------|----------|----------|----------|
| Idle | 600 s | 4 | 5 | 365 |
| Loaded (`stress-ng`) | 900 s | 4 | 5 | 197 |

**stress-ng:** `stress-ng --cpu 2 --io 1 --vm 1 --vm-bytes 70% --timeout 900s`

## Trunk health

- Haystack `check` PASS before and after gate (`HAYSTACK_INSECURE=1`)
- No FTDI/USB disconnect/reset in `kernel-usb-*.txt`
- MS/TP counter deltas: N/A (mini-device does not export CRC counters)

## Kernel

- `6.8.0-138-generic` PREEMPT_DYNAMIC, `CONFIG_HZ=1000`, `CONFIG_HIGH_RES_TIMERS=y`
- FTDI `latency_timer`: 16
