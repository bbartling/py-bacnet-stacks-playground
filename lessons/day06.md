# Day 06 — Vectors and ordered records

[Previous: Day 5](day05.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 7](day07.md)

**Week 1 · 45–90 minutes.** Prerequisites: Days 1–5, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Collect and inspect a small ordered list without out-of-bounds access.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day06/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

`Vec<T>` is a growable collection whose elements share a type. Its length describes initialized elements; capacity describes allocated storage and is not a count of records. Indexing assumes the index exists, while `.get()` makes absence explicit with `Option`. Today the records can be simple strings or integers. We will introduce richer structs after the Rust bridge.

## Tiny example

```rust
fn main() {
    let mut sizes = vec![12_u16, 18];
    sizes.push(24);
    println!("len={}, missing={:?}", sizes.len(), sizes.get(8));
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Build a Vec of three lab endpoint labels, append a fourth, and print the collection and its length.
- Ask for one valid and one invalid element position using `.get()`. Produce a friendly missing-element result.
- Empty the collection and demonstrate that inspecting its first element remains safe.

## Experiment

Remove the final element repeatedly until the vector is empty. Predict the result of the next `.pop()` before running it.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Order is preserved after appending.
- Empty and out-of-range cases are explicit.
- Your explanation distinguishes an element count from allocated capacity.

## Optional Python companion

Compare list indexing and `pop()` behavior on an empty list with Rust Option-returning methods.

## Stretch and reflection

Why would reserving a huge capacity based on an untrusted packet length be dangerous even if the vector starts empty?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-1) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 5](day05.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 7](day07.md)
