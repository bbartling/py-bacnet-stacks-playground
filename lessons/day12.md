# Day 12 — Counting events with maps

[Previous: Day 11](day11.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 13](day13.md)

**Week 2 · 45–90 minutes.** Prerequisites: Days 1–11, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Summarize repeated observations while keeping output deterministic.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day12/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A map can hold event counters, but the input sequence and the output order are separate concerns. Observing the same device twice does not necessarily mean two devices exist. Counts answer how often an event occurred; sets answer how many distinct identities appeared. Deterministic reports make regression tests and side-by-side captures easier to compare.

## Tiny example

```rust
fn main() {
    use std::collections::BTreeMap;
    let counts = BTreeMap::from([("timeout", 2), ("reply", 5)]);
    for (name, count) in &counts { println!("{name}: {count}"); }
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Count offline events labeled `reply`, `timeout`, and `invalid`; reject or separately count unknown labels.
- Print a stable sorted summary regardless of insertion order.
- Preserve the event total so it can be compared with the sum of category counts.

## Experiment

Reorder the input without changing its contents. Predict which results must stay the same and whether chronology can still be reconstructed.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Category totals agree with accepted input count.
- Reordered input gives the same summary.
- Unknown labels follow the documented policy.

## Optional Python companion

Produce the same counts with a plain dictionary loop, then compare against collections.Counter as an independent check.

## Stretch and reflection

Add a percentage but avoid division by zero on an empty input.

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-2) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 11](day11.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 13](day13.md)
