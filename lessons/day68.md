# Day 68 — Modbus RTU framing and CRC

[Previous: Day 67](day67.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 69](day69.md)

**Week 10 · 45–90 minutes.** Prerequisites: Days 1–67, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Explain the serial ADU and validate offline frames before touching hardware.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day68/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

Modbus RTU carries an address, application PDU and CRC. Serial silence helps delimit frames; an arbitrary host read boundary is not an RTU frame boundary. CRC byte transmission order is a protocol rule and differs from simply displaying a numeric checksum. TCP and RTU wrap related PDUs differently, so do not copy an entire TCP ADU onto a serial port.

## Tiny example

Compare [the RTU fixture](fixtures/modbus/README.md) with the TCP request for the same read. Identify what belongs to the application PDU and what belongs to each transport wrapper.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Write a Rust offline RTU verifier for the selected read-request/response subset. Include frame-size bounds and CRC validation.
- Use the serial-line guide for CRC and timing rules; test a known-answer frame independently of your encoder.
- Represent timestamps separately from bytes; do not infer physical silent intervals from a fixture with no timestamps.

## Experiment

Flip one data bit, truncate the CRC, and reverse its transmitted bytes. Each mutation should be distinguishable from a correct frame.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Valid fixture CRC agrees with an independent reference.
- Bad CRC is not treated as a valid exception.
- The report states that no physical timing was validated.

## Optional Python companion

Optionally compare the known-answer frame with an independent library; keep the Rust verifier primary.

## Stretch and reflection

Which timing behavior can a pseudo-terminal model, and which requires actual serial hardware?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-10) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 67](day67.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 69](day69.md)
