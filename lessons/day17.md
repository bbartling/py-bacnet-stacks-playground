# Day 17 — Files, text formats and repeatable inputs

[Previous: Day 16](day16.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 18](day18.md)

**Week 3 · 45–90 minutes.** Prerequisites: Days 1–16, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Read a small text file and write a result without confusing missing, empty and malformed input.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day17/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

Files let you repeat an experiment exactly. `read_to_string` assumes valid UTF-8 and reads the whole file; that is suitable for small trusted fixtures, not unlimited packet captures. A relative path is resolved from the process working directory, not from the Rust source file. Writing a report should not accidentally overwrite its input.

## Tiny example

```rust
fn main() {
    use std::path::Path;
    let input = Path::new("fixtures").join("sample.txt");
    println!("reading from {}", input.display());
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Read a supplied small UTF-8 file of one numeric value per line and display accepted/rejected line counts.
- Write the summary to a different path. State a 64 KiB fixture limit and enforce it before accepting the whole input; a bounded read is preferable to trusting a racing metadata check.
- Distinguish an empty file, a nonexistent file, invalid UTF-8 and an invalid number.

## Experiment

Run from a different working directory with the same relative input path. Then repeat with an explicit correct path and explain the result.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Source input remains unchanged.
- The output path and input path are reported.
- Missing and empty input have different outcomes.

## Optional Python companion

Compare `Path.read_text()` with binary reading on invalid UTF-8.

## Stretch and reflection

Explain when streaming line-by-line would be preferable and why individual line lengths still need a bound.

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-3) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 16](day16.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 18](day18.md)
