# Day 99 — UART, RS-485 and the electrical layer

[Previous: Day 98](day98.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 100](day100.md)

**Week 15 · 45–90 minutes.** Prerequisites: Days 1–98, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Plan a serial bench and explain the physical assumptions before sending bytes.

## Before you start

Dedicated Pi lab or the explicitly labeled VM/offline alternative. Hardware results must come from the actual hardware. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day99/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

UART defines serial character transmission; RS-485 defines electrical signaling characteristics. Protocols such as Modbus RTU and BACnet MS/TP impose additional timing and framing. Baud, parity, stop bits, termination, bias and transmit direction all affect behavior. A USB adapter introduces buffering and latency. A successful file write to a tty does not prove a valid waveform or a correctly timed bus transaction.

## Tiny example

Draw two isolated stations, the differential pair, signal reference/isolation arrangement, termination locations and adapter direction mechanism. Follow the actual adapter documentation; do not infer pin labels from a different model.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Write a Rust offline bench-config validator for baud, framing and adapter profile without opening a tty.
- Record hardware identifiers and wiring plan; read the destination repo Waveshare guide when using that adapter.
- Begin with passive observation only. The shared DIY bench remains at its documented 38400 hold; use a separate bench for experiments.

## Experiment

Compare a saved good trace with a trace documented as having a framing/wiring problem. Identify what cannot be concluded without electrical measurements.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- UART framing and network protocol framing are separate.
- Termination/bias/direction assumptions are documented from actual hardware.
- No new program transmits merely because config validation succeeded.

## Optional Python companion

Optional fixture inspection only; Rust owns configuration validation.

## Stretch and reflection

What instrument would let you distinguish electrical noise from a host-side read-chunk issue?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-15) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 98](day98.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 100](day100.md)
