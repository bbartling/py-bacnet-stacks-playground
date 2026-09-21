# Day 72 — BVLC functions and length validation

[Previous: Day 71](day71.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 73](day73.md)

**Week 11 · 45–90 minutes.** Prerequisites: Days 1–71, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Decode selected BACnet/IP wrappers before interpreting their NPDU payloads.

## Before you start

Offline fixtures first; isolated BACnet peers for live evidence. No occupied building network. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day72/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

Classic BACnet/IPv4 uses BVLC messages with a type, function and total length. Different functions have different bodies. Original-Unicast-NPDU and Original-Broadcast-NPDU carry an NPDU directly, while Forwarded-NPDU also carries the originating IP address and port. Control functions have other layouts. A decoder must dispatch by function instead of assuming every body starts with an NPDU.

## Tiny example

Inspect [the BACnet fixture notes](fixtures/bacnet/README.md). A BVLC length covers the entire BVLC message, including its header; that differs from the teaching envelope length on Day 36.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Implement a Rust view for classic BVLC type 0x81 and the three selected NPDU-carrying functions.
- Check total length against datagram length and require the extra origin-address bytes for Forwarded-NPDU.
- Report other functions as unsupported or recognized-control, without feeding them to the NPDU parser.

## Experiment

Change an Original-Broadcast function byte to Forwarded-NPDU without adding the required address bytes. Verify rejection rather than an invented origin.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Function-specific minimum lengths are enforced.
- Forwarded origin and UDP sender are separate fields.
- IPv6 BVLL is not assumed to use the same parser.

## Optional Python companion

Optionally compare BVLC fields with an independent BACnet decoder; the learning implementation remains Rust.

## Stretch and reflection

Why might the sender of a Forwarded-NPDU differ from the original application source?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-11) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 71](day71.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 73](day73.md)
