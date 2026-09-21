# Day 41 — MTU, fragmentation and capture filters

[Previous: Day 40](day40.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 42](day42.md)

**Week 6 · 45–90 minutes.** Prerequisites: Days 1–40, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Distinguish packet-size problems at IP from stream/application segmentation.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day41/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

MTU constrains a link-layer payload. IPv4 fragmentation can occur under its fragmentation rules; IPv6 routers do not fragment forwarded packets and instead use ICMPv6 Packet Too Big feedback. TCP segments a byte stream independently. BACnet APDU segmentation is yet another endpoint mechanism. Capture filters select saved packets using BPF; display filters select visible decoded packets afterward and use a different grammar.

## Tiny example

Capture filter: `icmp or icmp6`. Display filter: `icmp or icmpv6`. Neither expression alone captures every packet needed to reconstruct a PMTU incident; include the associated data flow when investigating.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Extend the inspector to identify IPv4 fragments and IPv6 Fragment headers, reporting identifiers and offsets without pretending to reassemble them.
- Create an offline report classifying complete, fragmented, truncated and unsupported inputs.
- On a disposable namespace topology, compare traffic across a smaller MTU, or analyze a recorded PMTU trace. Document the topology and expected ICMP evidence.

## Experiment

Predict whether reducing application payload, TCP write size or interface MTU changes the same boundary. Observe one controlled case; do not alter the host uplink MTU.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- TCP segmentation and IP fragmentation are named separately.
- Noninitial fragments are not interpreted as if they begin with transport headers.
- Capture and display filters are recorded separately.

## Optional Python companion

Generate a set of payload sizes for the Rust test client, without assuming each send creates one IP packet.

## Stretch and reflection

How could blocked ICMP feedback produce a size-dependent failure?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-6) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 40](day40.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 42](day42.md)
