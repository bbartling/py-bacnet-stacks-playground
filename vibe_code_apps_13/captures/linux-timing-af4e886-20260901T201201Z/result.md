# Linux timing gate result

**Gate result label:** measurement_complete

This gate records **host scheduler latency** (cyclictest), not Clause 9 wire turnaround.
Comparison value 1562.5 µs = 60 bit times @ 38400 baud — **informational host-risk only**,
not a universal response deadline and not T_frame_abort conformance.

## Assessments
- measurement_execution: pass
- stress_ng_execution: pass
- haystack_before: pass
- haystack_after: pass
- scheduling_threshold_assessment (idle): under
- scheduling_threshold_assessment (loaded): exceeded
- scheduling_threshold_assessment (overall): exceeded
- wire_timing_measured: false
- clause9_conformance: not_claimed

Note: cyclictest `-m` means **mlockall**, not one worker per CPU.
Historical fact preserved: capture recorded `git_dirty=true`.

## cyclictest-idle.txt
- threads: 1
- min: 4 us
- avg: 5 us (sample-weighted across threads)
- max: 239 us
- sched: SCHED_FIFO priority 80
- scheduling_threshold_assessment vs 1562.5 us: **under**
- host-risk indicator only (60 bit @ 38400) — not Clause 9 / not wire turnaround
- wire_timing_measured: false; clause9_conformance: not_claimed

## cyclictest-loaded.txt
- threads: 1
- min: 4 us
- avg: 11 us (sample-weighted across threads)
- max: 2639 us
- sched: SCHED_FIFO priority 80
- scheduling_threshold_assessment vs 1562.5 us: **exceeded**
- host-risk indicator only (60 bit @ 38400) — not Clause 9 / not wire turnaround
- wire_timing_measured: false; clause9_conformance: not_claimed

