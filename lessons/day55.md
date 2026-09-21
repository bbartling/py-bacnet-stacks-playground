# Day 55 — Bounded concurrency before async

[Previous: Day 54](day54.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 56](day56.md)

**Week 8 · 45–90 minutes.** Prerequisites: Days 1–54, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Serve several TCP clients without allowing unlimited threads or shared-state corruption.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day55/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A thread per connection is easy to understand but needs admission control. Shared mutable state needs synchronization, while socket waits should not hold a global lock that blocks everyone else. A connection limit bounds one resource, not every buffer or queued task. Shutdown should stop accepting new work and account for workers that are still active.

## Tiny example

A budget might be four concurrent clients, 1024 bytes per message, and a three-second idle deadline. These are separate limits; multiplying them does not automatically bound every allocation in the process.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Extend your Rust framed service to support at most four active clients with a documented overload response or immediate refusal policy.
- Maintain a shared completed-request counter and keep blocking socket operations outside the counter lock.
- Join worker threads on bounded shutdown and report unfinished work honestly.

## Experiment

Connect four slow clients and then a fifth. Verify that overload behavior is predictable and an unrelated completed client still updates the counter.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Active worker count never exceeds the configured limit.
- A stalled peer cannot hold the global state lock through network I/O.
- Shutdown has a documented deadline and outcome.

## Optional Python companion

Optionally launch concurrent peer processes and inspect the Rust server metrics.

## Stretch and reflection

Which costs would async remove, and which resource limits would still be necessary?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-8) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 54](day54.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 56](day56.md)
