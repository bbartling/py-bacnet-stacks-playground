# Day 59 — Cancellation, deadlines and task ownership

[Previous: Day 58](day58.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 60](day60.md)

**Week 9 · 45–90 minutes.** Prerequisites: Days 1–58, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Stop an async service without losing track of active work.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day59/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

Dropping a future cancels its further polling, but does not roll back side effects already performed. Dropping a JoinHandle does not necessarily stop the spawned task. A select branch can cancel another future, so inspect cancellation safety for the exact operation. Keep partial decoder state where it survives the waits that may be canceled. Shutdown has phases: stop admission, signal workers, then wait within a bound.

## Tiny example

Use a paper lifecycle: `accepting -> draining -> stopped`, with a separate final outcome for forced termination. These states describe service policy, not a replacement for Tokio primitives.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Add Ctrl-C or an explicit stop signal to the Rust service. Stop accepting new connections and notify active tasks.
- Track tasks using JoinSet or an equivalent owned collection and wait at most two seconds for draining.
- Preserve frame decoder state across timeouts or explicitly terminate the connection; do not silently discard part of a frame and continue.

## Experiment

Request shutdown while one client is idle and another is halfway through a frame. Report which tasks completed and which were canceled.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Task completion is observed rather than assumed from dropped handles.
- Shutdown duration is bounded.
- Partial-message behavior is documented and tested.

## Optional Python companion

Optionally hold a connection open from a small external peer while signaling the Rust server.

## Stretch and reflection

Which cleanup requires an explicit async shutdown method rather than Drop?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-9) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 58](day58.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 60](day60.md)
