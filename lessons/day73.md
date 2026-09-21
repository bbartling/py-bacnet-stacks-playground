# Day 73 — NPDU control fields and network messages

[Previous: Day 72](day72.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 74](day74.md)

**Week 11 · 45–90 minutes.** Prerequisites: Days 1–72, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Walk the optional NPDU fields using control bits and validated lengths.

## Before you start

Offline fixtures first; isolated BACnet peers for live evidence. No occupied building network. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day73/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

NPDU fields depend on control flags. Destination and source network address fields can be present or absent, and variable MAC lengths affect offsets. Hop count accompanies destination routing information. A network-message flag changes the meaning of the remaining payload from APDU to a network-layer message. BACnet addressing rules include special broadcast forms; do not substitute an IP-subnet interpretation.

## Tiny example

Draw an NPDU as `version | control | optional destination | optional source | optional hop count | payload`. The actual ordering and field validity come from the selected standard/stack reference, not from a fixed payload offset.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Implement a Rust NPDU header decoder for the documented classic subset, including source/destination presence and bounded address lengths.
- Classify application payload versus network message and retain priority/expecting-reply information where defined.
- Reject truncated optional fields, unsupported version and invalid reserved-bit combinations according to the reference.

## Experiment

Test a local application NPDU, a routed one and a network message. Mutate address lengths and destination/source presence bits independently.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- A field absent by control flag is not read.
- Hop-count position follows the validated optional fields.
- Network messages never go directly to the APDU parser.

## Optional Python companion

Optionally obtain independent decoder output for the same bytes from bacpypes3 or Wireshark.

## Stretch and reflection

Why should a router preserve application bytes it does not need to interpret?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-11) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 72](day72.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 74](day74.md)
