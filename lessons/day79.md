# Day 79 — ReadPropertyMultiple and APDU budgets

[Previous: Day 78](day78.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 80](day80.md)

**Week 12 · 45–90 minutes.** Prerequisites: Days 1–78, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Batch reads without assuming every peer accepts an arbitrarily large request or response.

## Before you start

Offline fixtures first; isolated BACnet peers for live evidence. No occupied building network. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day79/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

ReadPropertyMultiple can reduce overhead, but packet size and endpoint capability still matter. Maximum APDU size, segmentation support and service behavior are separate constraints. A successful batch can contain per-property failures, so aggregate success must not erase detail. A smaller request does not always bound response size if a property returns a large list.

## Tiny example

Compare reading several scalar properties with reading an entire object-list. Equal property counts do not imply equal response sizes.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Use the pinned stack to request a small read-only batch and preserve per-property outcomes.
- Create an explicit request/response budget policy based on observed peer capability and a conservative configurable limit.
- When a request is too large or unsupported, report the limitation and use a documented smaller-read fallback only where valid.

## Experiment

Increase a controlled simulator batch until it approaches a stated size limit. Capture actual encoded sizes; do not infer them from a Rust struct size.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Per-property errors are preserved.
- Encoded size is distinguished from item count.
- Segmentation support is checked rather than assumed.

## Optional Python companion

Optionally read the same properties independently for result comparison.

## Stretch and reflection

How would array-indexed reads help with a large property when supported?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-12) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 78](day78.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 80](day80.md)
