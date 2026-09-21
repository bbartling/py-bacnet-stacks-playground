# Day 10 — Parsing small text records

[Previous: Day 9](day09.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 11](day11.md)

**Week 2 · 45–90 minutes.** Prerequisites: Days 1–9, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Separate tokenization from validation for a deliberately simple input grammar.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day10/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A delimiter helps split text but does not make the resulting fields valid. Whitespace, empty fields and extra delimiters need policies. A simple `split` exercise is not a complete CSV parser because quoted commas and escaped quotes require more rules. Text addresses also have their own syntax; blindly splitting on a colon will later break IPv6.

## Tiny example

```rust
fn main() {
    let line = "alpha|ready";
    let fields: Vec<&str> = line.split('|').collect();
    println!("{fields:?}");
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Parse offline lines shaped `name,port`, with exactly two unquoted fields and no embedded commas. Trim surrounding field whitespace.
- Require a nonempty name and an explicit port in 1..=65535. Report line-specific errors.
- Keep the input grammar written beside the program; do not describe this as a general CSV library.

## Experiment

Try `pump,47808`, `pump,`, `,47808`, and `pump,47808,extra`. Then try a bracketed IPv6-looking name and explain why the name field itself is not an endpoint parser.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Extra fields are not silently ignored.
- A blank port does not become zero.
- Valid input has one normalized result.

## Optional Python companion

Compare your restricted grammar with Python csv.reader on a quoted comma, and explain the difference in scope.

## Stretch and reflection

Add comment-only lines with a clear policy for `#` inside a name.

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-2) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 9](day09.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 11](day11.md)
