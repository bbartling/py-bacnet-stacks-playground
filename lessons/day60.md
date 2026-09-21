# Day 60 — A two-connection TCP proxy

[Previous: Day 59](day59.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 61](day61.md)

**Week 9 · 45–90 minutes.** Prerequisites: Days 1–59, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Forward opaque bytes in both directions while preserving half-close behavior.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day60/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A TCP proxy terminates one connection and opens another. It does not forward original IP packets and cannot generally replay an in-flight stream safely. Bidirectional copying must allow one direction to finish while the other still has response bytes. Tokio provides copying primitives with documented shutdown and error semantics; using one does not remove the need for timeouts, admission limits and tests.

## Tiny example

```text
client TCP connection <-> proxy <-> backend TCP connection
client write EOF       -> backend write shutdown
client still reads     <- backend may still respond
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Build a Rust loopback proxy from one explicit listener to one configured backend. Treat payload bytes as opaque.
- Use or implement documented bidirectional-copy behavior; record bytes per direction and enforce connect/session limits.
- When either side errors, report that unflushed bytes may be lost. Never claim exactly-once application delivery.

## Experiment

Use a backend that waits for request EOF before responding. Compare direct connection with proxy traversal. Review the current copy_bidirectional API behavior rather than assuming both directions stop on the first EOF.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- The delayed response survives a client half-close.
- Connection failure is visible without an infinite retry loop.
- Byte totals are labeled by direction.

## Optional Python companion

Optionally supply the EOF-waiting backend as an independent Python test peer.

## Stretch and reflection

What would change if the proxy terminated TLS instead of forwarding encrypted bytes untouched?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-9) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 59](day59.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 61](day61.md)
