# Day 15 — Functions with clear contracts

[Previous: Day 14](day14.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 16](day16.md)

**Week 3 · 45–90 minutes.** Prerequisites: Days 1–14, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Extract reusable calculations whose inputs, outputs and failure conditions are explicit.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day15/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A function boundary is a promise to callers. It should describe the meaning of its arguments and the possible outcomes, not just their types. Pure functions are especially useful in network code because packet decoding and policy can be tested without sockets. Empty input often exposes an unstated assumption: a mean over no samples is not automatically zero.

## Tiny example

```rust
fn doubled(value: u32) -> u32 { value * 2 }
fn main() { println!("{}", doubled(6)); }
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Write a function that reports the largest item in a slice of small unsigned record lengths, using Option for an empty slice.
- Keep printing in the caller so the same calculation can be reused by tests.
- Document whether the input is modified; demonstrate that the caller can inspect it afterward.

## Experiment

Call the function with zero, one and several elements, including repeated maxima. Predict which cases return absence.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Empty input has no invented measurement.
- The original collection remains available and unchanged.
- Function documentation states the result meaning.

## Optional Python companion

Write a function with the same behavior and an explicit empty-input policy.

## Stretch and reflection

Why might returning Result be appropriate for a different function even when this one only needs Option?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-3) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 14](day14.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 16](day16.md)
