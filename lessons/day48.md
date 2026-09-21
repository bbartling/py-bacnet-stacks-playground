# Day 48 — Deterministic loss, delay and duplicate experiments

[Previous: Day 47](day47.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 49](day49.md)

**Week 7 · 45–90 minutes.** Prerequisites: Days 1–47, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Create a repeatable fault harness instead of relying on a naturally unreliable network.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day48/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A useful failure experiment changes one variable and records the schedule. Randomness can explore cases, but a seed or explicit event script is needed to reproduce them. Network emulation and application-level relays model different failures: dropping a received application datagram does not prove how a NIC behaves. Fault injection should be bounded by both time and volume.

## Tiny example

Example fault schedule: pass request 1; discard request 2; delay request 3 by 150 ms; duplicate reply 3 once. This is a test input, not a retry algorithm.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Write a Rust loopback UDP relay or simulated transport that applies a fixed schedule of pass/drop/delay/duplicate actions.
- Limit queued delayed packets to 32, payloads to the protocol maximum, and runtime to five seconds. Record over-limit drops.
- Feed your Day 44 client through it and report the client outcome independently from injected events.

## Experiment

Repeat the identical schedule three times. Compare outcome and attempt counts; explain any wall-clock timing variation without claiming bit-for-bit timing determinism.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- The schedule is saved with the result.
- Late delayed packets cannot leak into the next run.
- Queue exhaustion has an explicit policy.

## Optional Python companion

Optionally analyze the saved event log; implementing the fault engine twice is unnecessary.

## Stretch and reflection

Which failures are best tested with an in-memory fake clock rather than OS sleeps?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-7) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 47](day47.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 49](day49.md)
