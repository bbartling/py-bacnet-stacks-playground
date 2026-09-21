# Day 27 — Tests that can catch your own assumptions

[Previous: Day 26](day26.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 28](day28.md)

**Week 4 · 45–90 minutes.** Prerequisites: Days 1–26, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Build a small independent fixture suite instead of only testing round trips.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day27/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

An encoder and decoder can agree with each other while sharing the same bug. Known-answer tests come from an independently specified input or implementation. Unit tests target small behavior; integration tests exercise public interfaces. A useful negative test checks the error contract as well as avoiding a panic. Keep tests deterministic so a failure can be reproduced.

## Tiny example

```rust
fn main() {
    let decoded = u16::from_be_bytes([0x01, 0x02]);
    assert_eq!(decoded, 258);
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Add tests for one earlier parser using a literal valid fixture, a malformed fixture and boundary values.
- Add a CLI-level check for failure exit status and diagnostic context.
- Describe the origin of each expected result: hand calculation, specification or independent Python library.

## Experiment

Deliberately introduce a one-byte or one-boundary bug in a temporary copy and confirm a test fails. Restore the correct behavior afterward.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- At least one expected value is independent of the implementation under test.
- Tests include empty and excessive input.
- A failure reports which behavior regressed.

## Optional Python companion

Produce an expected value with struct or ipaddress where appropriate; do not duplicate the Rust algorithm mechanically.

## Stretch and reflection

Which valid-looking malformed input could still slip through your suite? Add one targeted case.

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-4) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 26](day26.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 28](day28.md)
