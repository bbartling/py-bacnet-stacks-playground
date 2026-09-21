# Day 24 — Borrowed packet views and lifetimes

[Previous: Day 23](day23.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 25](day25.md)

**Week 4 · 45–90 minutes.** Prerequisites: Days 1–23, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Return a view into a caller-owned buffer and explain why it remains valid.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day24/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A lifetime describes a relationship between references; it does not extend storage duration. A function returning part of an input slice can borrow that data without allocation. It cannot return a reference into a local Vec that is about to be dropped. Start with a single input lifetime and avoid elaborate generic designs until a real interface requires them.

## Tiny example

```rust
fn first_byte(bytes: &[u8]) -> Option<&u8> { bytes.first() }
fn main() { let data = [9_u8, 8]; println!("{:?}", first_byte(&data)); }
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Write a helper that returns a borrowed payload view after a caller-specified teaching-header size, or an error when too short.
- Document that the view borrows the original buffer and performs no payload copy.
- Use the returned view in the caller, then explain when the owning buffer may be mutated again.

## Experiment

In a scratch example, attempt to return a slice into a Vec created inside the helper. Read the diagnostic and choose a valid ownership design.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Header length zero and equal-to-buffer-length are handled.
- A larger header length is rejected.
- No unsafe code or leaked allocation is used to evade lifetime checking.

## Optional Python companion

Compare a Python bytes slice with a memoryview; discuss copying versus borrowed access.

## Stretch and reflection

When would an owned payload be the simpler and safer API?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-4) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 23](day23.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 25](day25.md)
