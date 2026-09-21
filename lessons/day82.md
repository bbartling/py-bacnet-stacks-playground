# Day 82 — COV subscriptions and renewal

[Previous: Day 81](day81.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 83](day83.md)

**Week 12 · 45–90 minutes.** Prerequisites: Days 1–81, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Compare subscription state with polling and make expiry/recovery visible.

## Before you start

Offline fixtures first; isolated BACnet peers for live evidence. No occupied building network. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day82/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

Change-of-value notification reduces repeated reads when supported, but introduces subscription lifetime, renewal and notification state. Confirmed and unconfirmed notifications have different acknowledgement behavior. A transport connection or successful initial subscription does not prove ongoing updates. Recovery should avoid duplicate subscriptions and should mark stale values instead of presenting them as current forever.

## Tiny example

A status record can include `last_update`, `subscription_expiry`, `renewal_outcome`, and `stale`. These are different clocks/events; do not derive all of them from the time the process started.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Inspect COV support in the pinned stack and simulator. If supported, build a bounded Rust subscription experiment for one disposable object.
- Track renewal and stale-data policy with at most four subscriptions; otherwise implement the same state in an offline event harness.
- Provide a documented polling fallback with a finite rate when appropriate, without labeling it COV.

## Experiment

Stop notifications or fail one renewal in the simulator. Observe how the result becomes stale and how recovery is reported.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Expired subscriptions are not shown as active.
- A repeated renewal does not create unbounded local state.
- Fixture-only and live COV evidence are clearly separated.

## Optional Python companion

Optionally use an independent simulator or observer; Rust owns the subscription experiment.

## Stretch and reflection

How would confirmed notifications affect traffic and acknowledgement handling on a slow network?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-12) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 81](day81.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 83](day83.md)
