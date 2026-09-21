# Day 83 — Writes, priority and ambiguous timeout

[Previous: Day 82](day82.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 84](day84.md)

**Week 12 · 45–90 minutes.** Prerequisites: Days 1–82, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Understand a controlled BACnet write and release without turning a timeout into a blind retry.

## Before you start

Offline fixtures first; isolated BACnet peers for live evidence. No occupied building network. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day83/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A commandable BACnet property can have a priority array and relinquish default. Writing a value at one priority differs from releasing that priority with NULL. Read-back helps observe effective state, but another priority can dominate it. A timeout can mean the request never arrived, the write occurred but the reply was lost, or the peer failed; automatic retry needs operation-specific reasoning.

## Tiny example

Use a disposable simulator object created for this exercise. Record initial effective value, priority slot state and relinquish behavior before the test. An occupied building controller is not a substitute fixture.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Create a Rust lab-only write command requiring an explicit target and opt-in flag, using public pinned stack APIs.
- Write one test value at a selected non-life-safety priority, read back the relevant state, then release that exact slot with NULL.
- Have a cleanup/recovery action for interrupted runs and report uncertain outcomes instead of retrying blindly.

## Experiment

Use a simulator/fault harness to lose the acknowledgement after applying the write. Compare local timeout with actual simulator state.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- The selected priority and target are explicit.
- The test ends with the exercised slot released or a clearly reported recovery task.
- A timeout is not reported as proof that no write occurred.

## Optional Python companion

Optionally observe simulator state independently. The primary operation is Rust.

## Stretch and reflection

Why can effective present-value differ from the value stored in the slot you just wrote?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-12) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 82](day82.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 84](day84.md)
