# Day 13 — Tuples, sets and identity

[Previous: Day 12](day12.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 14](day14.md)

**Week 2 · 45–90 minutes.** Prerequisites: Days 1–12, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Distinguish an observation from the identity used to deduplicate it.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day13/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A tuple groups a small fixed number of values; a set records uniqueness. Choosing the key is a design decision. Two observations with the same label can come from different endpoints, and one endpoint can be observed many times. Real BACnet identity and network addressing are different concepts; keep this lesson generic rather than assuming an IP address permanently identifies a device.

## Tiny example

```rust
fn main() {
    use std::collections::HashSet;
    let labels: HashSet<&str> = ["a", "b", "a"].into_iter().collect();
    println!("distinct={}", labels.len());
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Represent observations as `(label, textual_address)` tuples.
- Report observation count, unique labels, and unique addresses as three separate values.
- Include two labels sharing one address and one label appearing at two addresses.

## Experiment

Deduplicate first by label and then by full tuple. Explain what evidence each operation discards.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- The three counts can differ and are labeled.
- Identical tuples collapse predictably.
- No deduplication policy is described as universally correct.

## Optional Python companion

Use tuple keys in a Python set and compare the same three counts.

## Stretch and reflection

What extra field would you need to distinguish observations over time?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-2) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 12](day12.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 14](day14.md)
