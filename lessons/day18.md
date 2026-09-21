# Day 18 — Result, Option and error context

[Previous: Day 17](day17.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 19](day19.md)

**Week 3 · 45–90 minutes.** Prerequisites: Days 1–17, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Carry a failure from a low-level operation to a useful caller-facing diagnostic.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day18/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

Option models absence; Result models success or failure. The `?` operator returns early on error in a compatible function; it does not log or recover automatically. A useful diagnostic includes the operation and input context, such as file and line, without leaking secrets. `unwrap()` is convenient for a known test fixture but is not a recovery policy for untrusted input.

## Tiny example

```rust
fn parse_count(text: &str) -> Result<u16, std::num::ParseIntError> {
    let count = text.parse::<u16>()?;
    Ok(count)
}
fn main() { println!("{:?}", parse_count("many")); }
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Give your file loader an explicit result type and report filename plus line number for invalid records.
- Choose strict mode or continue-with-errors mode, document it, and keep successful records distinguishable from rejected ones.
- Return a nonzero exit status when the chosen contract considers the run unsuccessful.

## Experiment

Cause a file-open failure and a numeric-parse failure separately. Explain where each originates and which layer adds context.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- No malformed input is handled with a panic.
- Diagnostics identify the operation and location.
- Exit status matches the documented error policy.

## Optional Python companion

Catch narrow exception types rather than swallowing every Exception; compare where context is added.

## Stretch and reflection

Why might retrying a parse error never help while retrying a temporary transport failure sometimes does?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-3) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 17](day17.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 19](day19.md)
