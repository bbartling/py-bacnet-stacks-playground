# Day 04 — Types, comparisons and valid ranges

[Previous: Day 3](day03.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 5](day05.md)

**Week 1 · 45–90 minutes.** Prerequisites: Days 1–3, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Express a small configuration policy with booleans and avoid silent numeric narrowing.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day04/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

Rust has explicit integer widths. A `u16` can represent a UDP port number, but a listener port of zero has a special OS-selected meaning. Application policy may allow or reject it independently of numeric representation. Similarly, a BACnet network number and a UDP port can share a numeric type while obeying different rules. Casting with `as` is not input validation.

## Tiny example

```rust
fn main() {
    let count: u16 = 32;
    let permitted = count > 0 && count <= 64;
    println!("within batch limit: {permitted}");
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- For hard-coded signed integer inputs, report whether each is an allowed explicit listener port under your policy: 1 through 65535. State that zero is deliberately excluded today.
- Evaluate -1, 0, 1, 47808, 65535 and 65536. Use comparisons before converting values.
- Report two facts separately: numerically representable and allowed by this application.

## Experiment

Compare a value at a boundary with one immediately above it. Temporarily use an unchecked narrowing cast in a scratch example and explain why its result cannot certify validity.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- All six boundary cases have an expected classification.
- A negative input never becomes an accepted port through conversion.
- The policy for zero is written, not implicit.

## Optional Python companion

Use the same list and comparisons in Python. Explain why its flexible integer size does not remove protocol range limits.

## Stretch and reflection

How would an ephemeral-bind option change the policy without changing the port field width?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-1) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 3](day03.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 5](day05.md)
