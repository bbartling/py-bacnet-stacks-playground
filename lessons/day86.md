# Day 86 — BACnet route discovery and route tables

[Previous: Day 85](day85.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 87](day87.md)

**Week 13 · 45–90 minutes.** Prerequisites: Days 1–85, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Interpret BACnet network-layer route messages without applying IP routing rules to them.

## Before you start

Offline fixtures first; isolated BACnet peers for live evidence. No occupied building network. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day86/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

BACnet route discovery asks which router can reach a BACnet network number. Who-Is-Router-To-Network and I-Am-Router-To-Network are network-layer messages, not application Who-Is/I-Am discovery. A route includes a reachable network and a next-hop/port context. Dynamic state needs bounds and unavailable-route behavior; the selected stack procedures, not your IP prefix calculator, determine its semantics.

## Tiny example

Prepare two separate tables: IP destination prefix to gateway, and BACnet destination network number to router port/next hop. A BACnet network number is not a prefix length.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Write a Rust offline route-message reporter for selected supplied or independently captured network messages.
- Use the pinned stack to observe a small route table with at most a few declared lab networks.
- Document how unknown, duplicated or unavailable destinations are surfaced by that revision; do not invent stack guarantees.

## Experiment

Compare application Who-Is with Who-Is-Router-To-Network in a capture or fixture. Identify the NPDU network-message flag before examining the message type.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Application device discovery and network route discovery are distinguished.
- The next hop includes the necessary transport/port context.
- Unavailable route is visible, not silently treated as a local device.

## Optional Python companion

Optionally issue the independent network query from bacpypes3 if the pinned version supports it.

## Stretch and reflection

How should a topology change be reflected without retaining unlimited stale routes?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-13) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 85](day85.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 87](day87.md)
