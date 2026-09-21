# Day 45 — Unicast, broadcast and multicast interfaces

[Previous: Day 44](day44.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 46](day46.md)

**Week 7 · 45–90 minutes.** Prerequisites: Days 1–44, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Choose a delivery mode deliberately and observe its scope.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day45/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

Unicast targets an endpoint. IPv4 broadcast targets a broadcast domain under interface and subnet rules. Multicast uses group membership and routing policy; joining a group is not the same as binding a socket. IPv6 uses multicast rather than broadcast. Multi-interface hosts need explicit interface selection to avoid observing only half the experiment or transmitting on the wrong link.

## Tiny example

Create a topology note with `sender interface`, `local address`, `destination address`, `port`, and `delivery mode` before running anything. A wildcard bind is not itself an instruction to join every multicast group.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Extend a Rust UDP probe with an explicit unicast mode and a separately selected lab-only IPv4 broadcast mode.
- Add one multicast receiver exercise with an explicitly recorded group and interface; use the scope rules from the selected protocol/test group.
- Bound messages to ten and keep the experiment on an isolated segment. No subnet scanning.

## Experiment

Compare an ordinary unicast receiver with a group member. Record when the OS or lab environment does not support the chosen multicast path rather than treating silence as proof of no peers.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Mode and egress interface are visible in the report.
- IPv6 tests use multicast, not an invented broadcast address.
- The capture identifies the actual destination address.

## Optional Python companion

Optionally act as the second receiver to distinguish implementation bugs from group/interface setup.

## Stretch and reflection

Why can multicast loopback settings change same-host observations?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-7) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 44](day44.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 46](day46.md)
