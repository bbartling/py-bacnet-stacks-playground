# Day 88 — Broadcast scope and loop bounds

[Previous: Day 87](day87.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 89](day89.md)

**Week 13 · 45–90 minutes.** Prerequisites: Days 1–87, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Build a BACnet broadcast test matrix and explain why forwarding must be bounded.

## Before you start

Offline fixtures first; isolated BACnet peers for live evidence. No occupied building network. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day88/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

Local, remote and global broadcasts have different BACnet scopes. Forwarding decisions depend on network-layer addressing, ingress context and topology. A UDP broadcast arriving on one interface is not permission to rebroadcast it everywhere. Hop-count exhaustion and loop prevention matter especially when several routers or BBMDs can replicate traffic. Avoid inventing a universal deduplication rule from payload equality alone.

## Tiny example

A test matrix names input scope, ingress port, intended egress ports and excluded ports. The expected results should be justified against the applicable procedure, not inferred solely from one implementation run.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Create table-driven Rust tests or a harness around the pinned router for local, remote and global broadcast cases.
- Include hop exhaustion and unavailable destination cases with bounded message counts.
- Record observed forwarding separately from expected forwarding, including ingress suppression and duplicates.

## Experiment

Use a tiny finite message count in an isolated topology. Do not create an uncontrolled live loop to “see what happens”; exercise cyclic cases through bounded fixtures or a controlled simulator.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Every expected egress has a stated reason.
- No packet can keep the test running indefinitely.
- Identical application payloads are not automatically treated as the same transaction.

## Optional Python companion

Optionally compare captured counts or create a single independent test packet.

## Stretch and reflection

What is the difference between suppressing a duplicate and incorrectly dropping a legitimate repeated request?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-13) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 87](day87.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 89](day89.md)
