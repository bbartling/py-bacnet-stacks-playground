# Day 44 — Request correlation and retry budgets

[Previous: Day 43](day43.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 45](day45.md)

**Week 7 · 45–90 minutes.** Prerequisites: Days 1–43, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Match replies to a specific request and stop within an overall deadline.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day44/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

UDP does not connect a reply to an earlier application request. An application identifier and peer address provide correlation, but identifiers can wrap or be reused. Retries are safe only when the operation and peer behavior tolerate duplicates. A per-receive timeout alone can be extended indefinitely by irrelevant traffic; an overall deadline bounds the transaction.

## Tiny example

```text
request id 17 -> intended peer
reply id 16   -> stale, not completion
reply id 17 from another peer -> unrelated
reply id 17 from intended peer -> candidate completion
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Add the request identifier defined in [the field messenger format](WIRE_FORMATS.md#field-messenger) to a read-only status request.
- Allow at most three sends within a two-second overall budget. Discard wrong-peer, wrong-ID and malformed replies while preserving the deadline.
- Report attempts and final outcome; keep late replies from completing the next request.

## Experiment

Use a second lab process to send an unrelated reply before the correct one, then test no correct reply at all.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Unrelated traffic cannot keep the request alive forever.
- Duplicate matching replies count as one completion.
- Timeout is distinguished from an explicit peer error.

## Optional Python companion

Optionally build only the fault sender in Python; the transaction implementation stays Rust.

## Stretch and reflection

How would you avoid confusing a very old reply with a newly reused identifier?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-7) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 43](day43.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 45](day45.md)
