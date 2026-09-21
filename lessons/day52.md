# Day 52 — Incremental framing and bounded buffers

[Previous: Day 51](day51.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 53](day53.md)

**Week 8 · 45–90 minutes.** Prerequisites: Days 1–51, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Decode multiple application messages from an arbitrary TCP byte stream.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day52/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A framing layer turns a byte stream into records. Delimiters are convenient for text but require escaping or restricted payloads. Length prefixes work for opaque bytes but must be validated before allocation. Keep incomplete buffered state separate from invalid input. At final EOF, an incomplete frame becomes truncation. Use the same decoder in memory and on sockets.

## Tiny example

Use [the TCP record framing contract](WIRE_FORMATS.md#tcp-record-service): two-byte big-endian payload length, followed by that many bytes. The prefix excludes itself; a maximum keeps buffering finite.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Implement an incremental Rust frame decoder with maximum payload 1024 bytes, preserving leftover bytes after one frame.
- Support zero-length payload at the framing layer; application commands may reject it separately.
- Reject oversized lengths immediately and distinguish incomplete input from malformed input and final truncation.

## Experiment

Concatenate two frames and split the resulting bytes at every possible boundary. Compare decoded frame sequence across splits.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Two frames in one read do not merge into one message.
- One frame across many reads is not rejected prematurely.
- Oversize input cannot trigger unbounded allocation.

## Optional Python companion

Optionally generate length-prefixed fixtures with struct.pack; no duplicate decoder needed.

## Stretch and reflection

Compare memory growth under a peer that sends a valid prefix very slowly.

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-8) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 51](day51.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 53](day53.md)
