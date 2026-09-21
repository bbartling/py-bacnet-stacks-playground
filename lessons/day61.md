# Day 61 — Backend selection and health policy

[Previous: Day 60](day60.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 62](day62.md)

**Week 9 · 45–90 minutes.** Prerequisites: Days 1–60, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Route new TCP connections predictably without replaying existing streams.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day61/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A connection-level routing decision chooses a backend before opaque forwarding begins. A health check is evidence about a particular probe at a particular time, not a promise that the next request succeeds. New connections may choose another healthy backend; an existing byte stream cannot be moved safely without an application protocol that supports it. Configuration needs validation before listeners become active.

## Tiny example

Example configuration meaning: listener A selects backend A; listener B selects backend B. Round-robin within a backend group is a later extension, not required for a useful traffic switch.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Support two explicit listener-to-backend mappings and reject duplicate listeners or invalid endpoints.
- Apply a bounded connect timeout and an observable unavailable-backend outcome.
- If adding health checks, cap check frequency and outstanding probes; state whether the check proves TCP acceptance or application health.

## Experiment

Stop backend A while B remains active. Verify that B traffic continues and an existing A connection is not replayed to B.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Routing is determined by validated configuration.
- A failed backend does not stall unrelated listeners.
- In-flight stream retry is not automatic.

## Optional Python companion

Optionally launch identifiable test backends that return different fixed labels.

## Stretch and reflection

Add round-robin selection for new connections and explain how you would test fairness without assuming exact OS scheduling.

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-9) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 60](day60.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 62](day62.md)
