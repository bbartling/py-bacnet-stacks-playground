# Day 67 — Registers are words, not engineering values

[Previous: Day 66](day66.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 68](day68.md)

**Week 10 · 45–90 minutes.** Prerequisites: Days 1–66, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Keep protocol data separate from vendor-specific interpretation.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day67/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

Modbus distinguishes coils, discrete inputs, input registers and holding registers. A register is a 16-bit word; a vendor may combine words into integers, floats or bit fields with documented word order and scaling. The wire protocol specifies bytes within a register, while a vendor register map must explain multi-register meaning. Guessing from a plausible temperature is not verification.

## Tiny example

Two raw words `0x0001` and `0x0002` can be displayed without claiming a float or scaled value. A mapping table must identify address notation, function, word order, signedness, scale and units before interpretation.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Extend the Rust report to show raw register hex and optional interpreted values using an explicit small mapping configuration.
- Support one documented signed integer mapping and one two-register mapping; no automatic word-order guessing.
- Reject insufficient register data and retain raw words in the result.

## Experiment

Apply two different word-order settings to the same fixture and show how both can produce numbers while only the configured one is intended.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Raw data is available alongside interpretation.
- Address notation conversion is documented.
- Units and scale come from configuration, not inferred from the value.

## Optional Python companion

Optionally verify a mapping with Python struct using explicit endianness.

## Stretch and reflection

How would you mark an unavailable or out-of-range engineering value without replacing it with zero?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-10) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 66](day66.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 68](day68.md)
