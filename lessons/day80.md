# Day 80 — BACnet APDU segmentation on the wire

[Previous: Day 79](day79.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 81](day81.md)

**Week 12 · 45–90 minutes.** Prerequisites: Days 1–79, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Explain APDU segmentation independently of TCP and IP fragmentation.

## Before you start

Offline fixtures first; isolated BACnet peers for live evidence. No occupied building network. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day80/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

BACnet can split a confirmed application message across segmented APDUs when endpoint capabilities and service procedures permit it. Sequence numbers, windowing and SegmentACK control the transaction. These are not TCP sequence numbers. An NPDU router forwards traffic between BACnet networks; it does not automatically make an endpoint support segmentation or reassemble every application response on its behalf.

## Tiny example

Prepare three separate diagrams: an IP datagram split into fragments; a TCP stream carried in segments; a BACnet service response carried in segmented APDUs. Name the component responsible for reassembly in each.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Write a Rust offline timeline reader for labeled segmentation events from [fixtures/bacnet](fixtures/bacnet/README.md). This is event analysis, not a complete wire implementation.
- Identify request/response direction, invoke ID, sequence number, window, more-follows and acknowledgement events where the trace provides them.
- State which endpoint capabilities and exact upstream APIs would be required for a live test.

## Experiment

Compare a complete event trace with one missing a segment. Predict whether the transaction can finish and which evidence is insufficient to claim success.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Sequence/window fields are not confused with TCP headers.
- The report states event-fixture provenance.
- The appliance is not advertised as segmentation-capable based on this lesson.

## Optional Python companion

Optionally inspect timeline CSV; the analyzer remains Rust.

## Stretch and reflection

What would you need to capture to distinguish a lost segment from a lost acknowledgement?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-12) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 79](day79.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 81](day81.md)
