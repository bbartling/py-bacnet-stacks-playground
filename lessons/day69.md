# Day 69 — Independent Modbus interoperability

[Previous: Day 68](day68.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 70](day70.md)

**Week 10 · 45–90 minutes.** Prerequisites: Days 1–68, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Cross-check your implementation against another endpoint and enforce a polling budget.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day69/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

Two sides written from the same assumptions can interoperate and still be wrong. An independent peer tests a different implementation. Polling adds scheduling: slow responses should not cause unlimited overlapping requests or burst catch-up. Read-only work is the baseline. Exception and transport errors deserve counters separate from successful polls.

## Tiny example

A finite poll plan can specify ten reads, one outstanding transaction, a one-second period and a two-second overall transaction budget. Explain what happens to the schedule when a read takes longer than the period.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Run the Rust client against a maintained simulator with fixed registers and a recorded version.
- Collect ten bounded read attempts with latency and outcome; skip missed schedule slots rather than launching an unbounded catch-up burst.
- Compare normal values and one exception with another client or the simulator configuration.

## Experiment

Delay the peer, then stop it during the run. Verify that attempts stay bounded and shutdown does not wait forever.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Independent peer identity/version is recorded.
- No uncontrolled request overlap occurs.
- Timeout, exception and normal counts reconcile with attempts.

## Optional Python companion

Optional: Python may be the independent simulator or comparator, not the main polling implementation.

## Stretch and reflection

How would many devices change a fair polling schedule without increasing per-device concurrency?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-10) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 68](day68.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 70](day70.md)
