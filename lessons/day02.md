# Day 02 — Variables, units and packet budgets

[Previous: Day 1](day01.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 3](day03.md)

**Week 1 · 45–90 minutes.** Prerequisites: Days 1–1, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Use explicit numeric types and arithmetic to estimate a bounded message budget.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day02/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A number without a unit is easy to misuse. Bytes, bits, milliseconds and packets are different quantities even when Rust gives them the same integer representation. Immutable bindings prevent accidental reassignment; `mut` expresses intended change. Integer division discards a fractional remainder. A rate calculation is an estimate, not a statement about actual Ethernet overhead or delivery latency.

## Tiny example

```rust
fn main() {
    let samples: u32 = 4;
    let bytes_per_sample: u32 = 3;
    println!("{} payload bytes", samples * bytes_per_sample);
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- For hard-coded counts, calculate payload bytes, header bytes and total bytes for 12 messages containing 8 payload bytes and a 4-byte teaching header each. Label every output unit.
- Calculate a 5-second average payload byte rate separately from the total wire-format byte rate. Do not call either Ethernet throughput.
- Repeat with zero messages and with a non-even division; explain integer vs floating-point output.

## Experiment

Change a header size but keep the payload unchanged. Predict which totals should change. Deliberately assign a negative number to an unsigned binding and explain the diagnostic.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Zero messages produces zero bytes.
- The total includes a header for each message.
- The explanation distinguishes bits per second from bytes per second.

## Optional Python companion

Calculate the same totals using Python integers and `/` versus `//`. Identify one difference in the languages rather than copying every line.

## Stretch and reflection

What information would be missing if you wanted to estimate real Ethernet traffic? List overhead sources without adding guessed constants.

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-1) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 1](day01.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 3](day03.md)
