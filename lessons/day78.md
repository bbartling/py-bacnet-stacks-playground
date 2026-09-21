# Day 78 — Confirmed transactions and invoke-ID lifetime

[Previous: Day 77](day77.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 79](day79.md)

**Week 12 · 45–90 minutes.** Prerequisites: Days 1–77, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Model bounded confirmed-service state and make stale responses harmless.

## Before you start

Offline fixtures first; isolated BACnet peers for live evidence. No occupied building network. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day78/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A confirmed transaction has identity, peer context, timers and an outcome. Retransmission policy belongs to the transaction layer; adding another retry loop around a stack that already retries can multiply traffic. Invoke IDs are finite and can be reused only with a considered lifetime policy. Late replies, duplicates and cancellation should not silently mutate a completed result.

## Tiny example

Use a paper timeline with `start`, `send`, `timeout`, `retry`, `reply`, and `finish`. Record whether the selected stack or your wrapper owns each event before writing additional retry behavior.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Inspect the pinned stack timeout/retry configuration and expose those settings in a read-only Rust experiment.
- Build an offline transaction tracker keyed by peer/context plus invoke ID, capped at eight outstanding entries.
- Expire state by a monotonic deadline; ignore or report late/duplicate replies after completion.

## Experiment

Inject reply-before-timeout, timeout-before-reply, duplicate-reply and cancellation event orders using a fake clock. Keep this simulator separate from live stack internals.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Each transaction completes at most once.
- The retry owner is explicit.
- Expired state cannot grow without bound.

## Optional Python companion

Optionally generate event lists; run the transaction state machine in Rust.

## Stretch and reflection

What extra guarantee would be needed before reusing an ID immediately after cancellation?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-12) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 77](day77.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 79](day79.md)
