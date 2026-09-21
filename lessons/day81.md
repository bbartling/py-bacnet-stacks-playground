# Day 81 — A bounded segmentation simulator

[Previous: Day 80](day80.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 82](day82.md)

**Week 12 · 45–90 minutes.** Prerequisites: Days 1–80, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Test a small explicitly scoped reassembly model with a fake clock.

## Before you start

Offline fixtures first; isolated BACnet peers for live evidence. No occupied building network. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day81/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A simulator lets you examine event order without waiting on real serial timing. Keep the model narrower than full BACnet conformance: a selected receive-side window, one transaction and a declared ordering policy. Sequence numbers wrap, so ordinary integer ordering can be misleading. Byte, segment, transaction and lifetime limits all matter. A correct simulator does not prove the stack uses the same state machine.

## Tiny example

Use [the segmentation exercise contract](WIRE_FORMATS.md#segmentation-simulator). It defines expected events and a receive-window-one subset, leaving data structures and control flow to you.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Implement the receive-window-one Rust model with one active peer/invoke context, modulo-256 sequence handling, and a fake monotonic clock.
- Bound total payload to 4096 bytes and the transfer to 32 accepted segments; expire after a declared deadline.
- Handle duplicate previous segment, unexpected sequence, wrong context and timeout according to the written contract; no live network I/O.

## Experiment

Run an event sequence crossing 255 to 0, then add a duplicate and an out-of-order segment. Compare completion and retained bytes.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Duplicates do not append payload twice.
- Wraparound behaves according to the declared expected sequence.
- Wrong-context events cannot extend lifetime or grow storage.

## Optional Python companion

Optionally supply table-driven event fixtures; no duplicate state-machine implementation required.

## Stretch and reflection

List the missing sender, retransmission and larger-window behaviors before calling this a full segmentation implementation.

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-12) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 80](day80.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 82](day82.md)
