# Linux timing gate result

**Verdict:** pass

Scheduling latency below 1,562.5 µs (60 bit times @ 38400 baud) is a **host-risk**
measurement only — not BACnet Clause 9 wire-timing conformance.

## cyclictest-idle.txt
- threads: 1
- min: 4 us
- avg: 5 us (sample-weighted across threads)
- max: 239 us
- sched: SCHED_FIFO priority 80
- vs 1562 us (60 bit @ 38400): scheduling-risk indicator only — not Clause 9 conformance

## cyclictest-loaded.txt
- threads: 1
- min: 4 us
- avg: 11 us (sample-weighted across threads)
- max: 2639 us
- sched: SCHED_FIFO priority 80
- vs 1562 us (60 bit @ 38400): scheduling-risk indicator only — not Clause 9 conformance

