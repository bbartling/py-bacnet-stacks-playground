# Day 11 — Maps and explicit missing values

[Previous: Day 10](day10.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 12](day12.md)

**Week 2 · 45–90 minutes.** Prerequisites: Days 1–10, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Use keyed lookup without inventing a default that could be mistaken for real data.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day11/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

`HashMap<K,V>` associates keys with values. `.get()` returns an Option because a key may not exist. Missing data, a numeric zero, and an error are different facts. In a building network, treating a missing measurement as zero can look like a genuine reading. Hash-map iteration order is not a stable output contract.

## Tiny example

```rust
fn main() {
    use std::collections::HashMap;
    let mut counts = HashMap::new();
    counts.insert("udp", 4_u32);
    println!("tcp={:?}", counts.get("tcp"));
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Store three endpoint names and configured port numbers in a HashMap.
- Look up a present name and an absent name, printing a different outcome for each.
- Insert the same key twice and record whether it replaces the old value; choose a duplicate policy for your eventual file loader.

## Experiment

Give one key a value that is valid but unusual. Demonstrate that it is still different from the missing key.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Missing lookup never claims a successful endpoint.
- Duplicate-key behavior is explained.
- No test relies on HashMap display order.

## Optional Python companion

Compare dictionary indexing, `.get()`, and membership tests for the same absent name.

## Stretch and reflection

What information should be retained when duplicate configuration entries disagree?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-2) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 10](day10.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 12](day12.md)
