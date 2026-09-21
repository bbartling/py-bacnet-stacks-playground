# Day 90 — VLANs, NAT, BACnet/IPv6 and BACnet/SC

[Previous: Day 89](day89.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 91](day91.md)

**Week 13 · 45–90 minutes.** Prerequisites: Days 1–89, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Choose the right boundary mechanism and identify where protocol support changes.

## Before you start

Offline fixtures first; isolated BACnet peers for live evidence. No occupied building network. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day90/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A VLAN separates link-layer domains; an IP subnet describes network-layer addressing; a BACnet network number belongs to BACnet routing. NAT changes address/port representation and can interact badly with protocols carrying addresses inside payloads. BACnet/IPv6 has different BVLL behavior from classic IPv4. BACnet/SC uses secure connections and hub-related topology; it is not achieved by putting ordinary UDP packets behind an HTTPS dashboard.

## Tiny example

Create four labeled boxes: Ethernet/VLAN, IPv4/IPv6 routing, BACnet network routing, and secure application transport. Place each proposed configuration change in the box it actually affects.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Extend your Rust topology/report format with separate VLAN ID, IP prefix, BACnet network number and transport capability fields.
- For three supplied scenarios, state whether an IP router, BBMD, BACnet router or supported BACnet/SC component is required.
- Inspect the selected stack capability and docs before proposing live IPv6/SC tests; unsupported cases remain analysis exercises.

## Experiment

Compare a packet before/after controlled IPv4 NAT in the namespace lab, or an offline trace. Check whether an embedded application address changes automatically—it generally does not without protocol-aware handling.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- IPv4 BVLC parser is not reused blindly for IPv6/SC.
- Management HTTPS is not advertised as BACnet/SC support.
- The capability table distinguishes implemented, tested and unknown.

## Optional Python companion

Optional Python can validate input addresses; no semantic-modeling layer is required.

## Stretch and reflection

What certificate identity and trust questions would a real BACnet/SC lab add?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-13) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 89](day89.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 91](day91.md)
