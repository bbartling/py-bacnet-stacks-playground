# Day 09 — Decisions and finite state

[Previous: Day 8](day08.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 10](day10.md)

**Week 2 · 45–90 minutes.** Prerequisites: Days 1–8, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Express a small offline retry policy using conditional branches and a bounded loop.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day09/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A branch selects behavior; a state describes what is true between events. Network programs often wait for success, retry after a timeout, or stop on cancellation. A loop must explain why it eventually stops. Avoid mixing a retry count with an overall time budget as though they were interchangeable. Today model events as text values; actual timers arrive later.

## Tiny example

```rust
fn main() {
    let attempts = 2;
    let label = if attempts < 3 { "budget remains" } else { "stop" };
    println!("{label}");
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Consume a fixed sequence containing `timeout`, `timeout`, `success`. Report the outcome and number of attempted operations.
- Limit attempts to three; a longer timeout sequence must end in an explicit exhausted result.
- An unrecognized event is invalid input, not a success.

## Experiment

Move success to the first position, then remove it. Predict the output before each run and inspect whether anything after success is still processed.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Success ends processing immediately.
- Three timeouts produce exhaustion with no fourth attempt.
- Unknown input has a documented outcome.

## Optional Python companion

Model the same event list in Python and compare counts.

## Stretch and reflection

Explain how cancellation differs from a retryable timeout. Add it as an event only after the baseline works.

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-2) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 8](day08.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 10](day10.md)
