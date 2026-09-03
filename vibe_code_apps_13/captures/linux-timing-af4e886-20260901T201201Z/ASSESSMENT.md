# Assessment correction — 201201Z Linux timing capture

**Date:** 2026-09-03  
**Raw evidence:** preserved (`cyclictest-idle.txt`, `cyclictest-loaded.txt`, histograms, stress-ng logs)  
**Pin:** `af4e88680c51eb4da64dac47f0540a35bf184732` (frozen)

## What was wrong

1. Docs claimed loaded max **2639 µs** was **under** the **1562.5 µs** comparison value. **2639 > 1562.5** → must be **exceeded**.
2. Bare gate **PASS** could be read as Clause 9 / wire-timing compliance. The gate only proved cyclictest produced `T:` lines + stress-ng exit 0.
3. cyclictest measures **scheduler latency**, not Clause 9 wire turnaround.
4. `-m` was easy to misread as SMP workers; it means **mlockall**. Capture used **one** cyclictest worker.
5. The 60-bit interval is **not** a universal response deadline / not blanket `T_frame_abort`.

## Corrected labels

| Field | Value |
|-------|-------|
| result / gate label | `measurement_complete` |
| measurement_execution | pass |
| stress_ng_execution | pass |
| haystack_before / after | pass |
| scheduling_threshold_assessment | **exceeded** (driven by loaded max 2639) |
| wire_timing_measured | false |
| clause9_conformance | not_claimed |

## On-wire qualification

**DEFERRED** until a suitable high-impedance logic analyzer / oscilloscope / differential RS-485 analyzer is available. Do **not** rerun cyclictest and call it Clause 9 evidence. Do **not** add a third Waveshare C as a passive analyzer (onboard ~120 Ω termination).
