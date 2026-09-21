# Day 20 — Your Day 19 project, now in Rust

[Previous: Day 19](day19.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 21](day21.md)

**Week 3 · 45–90 minutes.** Prerequisites: Your completed Day 19 Python project, or the Rust version for new learners. Days 20–28 are the bridge; completed legacy lessons count.

## Goal

Use your own completed project to learn Rust by preserving behavior across languages.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day20/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

The port is a behavior comparison, not a line-for-line syntax conversion. Rust makes ownership, numeric types and error paths explicit. Work through compiler feedback in small changes. A learner who already completed Day 19 in Rust can refactor its public interface and add an independent Python check instead of duplicating the exercise. Use your existing source as the baseline; there is no need to repeat completed foundations.

## Tiny example

```rust
fn main() {
    let sample = "18.5";
    let parsed: Result<f64, _> = sample.parse();
    println!("{parsed:?}");
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Create a Rust version of your Day 19 tool with the same documented valid-input and invalid-input policies.
- Use Result for fallible work and Option or an explicit no-data outcome for an empty accepted set.
- Keep the old implementation and compare both against the same fixtures, including a finite-number check.

## Experiment

Run both tools on the Day 19 valid and malformed fixtures. Compare numeric results with a written floating-point tolerance rather than requiring identical presentation.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Both tools agree on which rows are accepted.
- Missing and empty input remain different.
- Write down three Rust compiler messages you encountered and what changed in your understanding.

## Optional Python companion

Use your old Python implementation as the independent peer. Do not alter it merely to match a new Rust bug.

## Stretch and reflection

Which differences are intentional interface improvements, and which are regressions? Record them explicitly.

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-3) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 19](day19.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 21](day21.md)
