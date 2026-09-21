# Day 08 — Loops, ranges and bounded work

[Previous: Day 7](day07.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 9](day09.md)

**Week 2 · 45–90 minutes.** Prerequisites: Days 1–7, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Use loops to summarize records and make a finite work budget visible.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day08/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A range expresses repetition without manually updating a counter. `0..n` excludes n; `0..=n` includes it. Iterating by reference preserves the collection for later use. Network tools eventually need limits on requests, records and retries; an innocent off-by-one can change the rate or contact an unintended endpoint. Today use only offline data.

## Tiny example

```rust
fn main() {
    let lengths = [3_u32, 5, 7];
    for (index, length) in lengths.iter().enumerate() {
        println!("record {index}: {length} bytes");
    }
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Given a vector of captured-message lengths, calculate count and total bytes with explicit loops.
- Print a human-friendly record number starting at 1 while explaining the zero-based index.
- Generate exactly five proposed poll slots, without sleeping or sending packets.

## Experiment

Change an exclusive range to an inclusive range and predict the extra iteration. Repeat with an empty vector.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Counts equal the number of processed records.
- The empty collection has a defined summary.
- No loop sends real traffic or has an accidental unbounded termination condition.

## Optional Python companion

Use a plain Python for loop and range; avoid comprehensions for this exercise.

## Stretch and reflection

Add a maximum of three processed records and report how many were left out.

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-2) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 7](day07.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 9](day09.md)
