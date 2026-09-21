# Day 89 — BBMD and foreign-device registration

[Previous: Day 88](day88.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 90](day90.md)

**Week 13 · 45–90 minutes.** Prerequisites: Days 1–88, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Explain broadcast distribution across IP subnets without confusing it with BACnet network routing.

## Before you start

Offline fixtures first; isolated BACnet peers for live evidence. No occupied building network. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day89/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

Classic BACnet/IP broadcast distribution can use BBMDs to carry broadcasts across IP subnet boundaries. BDT configuration and FDT registration have different roles. A foreign-device registration has a lifetime and renewal behavior. Forwarded-NPDU carries an origin distinct from the current UDP sender. This arrangement need not mean a BACnet NPDU router has crossed to a different BACnet network number.

## Tiny example

Draw two IP subnets participating in one BACnet/IP network via BBMD distribution, then a separate drawing with two BACnet network numbers joined by an NPDU router.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Use an established BBMD implementation or recorded trace; do not assume the DIY router implements BBMD/FDR.
- Write a Rust offline analyzer showing registration, result, forwarded origin and expiry-related events where available.
- Create a configuration/evidence table distinguishing BDT entries, foreign registrations and BACnet route entries.

## Experiment

Let a disposable foreign registration expire without renewal or inspect an equivalent trace. Observe the effect on broadcast reception separately from direct unicast reachability.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- IP subnet boundary and BACnet network boundary are not equated.
- Origin address and current sender remain separate.
- Support claims name the actual BBMD implementation and version.

## Optional Python companion

Optional bacpypes3 may provide a foreign-device peer when supported; Rust remains the analyzer.

## Stretch and reflection

Why can NAT complicate advertised origin/address behavior even if ordinary UDP requests appear to work?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-13) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 88](day88.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 90](day90.md)
