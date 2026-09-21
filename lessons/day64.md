# Day 64 — Modbus TCP: MBAP, ADU and PDU

[Previous: Day 63](day63.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 65](day65.md)

**Week 10 · 45–90 minutes.** Prerequisites: Days 1–63, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Annotate a Modbus request without confusing its framing with TCP segments.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day64/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A Modbus application PDU begins with a function code and function data. Modbus TCP wraps it with MBAP: transaction ID, protocol ID, length and unit ID. The length counts unit ID plus PDU, so a complete ADU length is six plus that field. TCP still supplies a byte stream; one read need not contain the complete MBAP header. The Modbus TCP form does not carry an RTU CRC.

## Tiny example

Inspect the request in [fixtures/modbus](fixtures/modbus/README.md). Identify MBAP fields, the read function, starting address and quantity using the official application/TCP guides. Fixture bytes are a contract example, not a complete parser.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Implement a Rust MBAP header view using the length rules from the official guide.
- Require protocol ID zero for this Modbus subset and validate a bounded total ADU size before exposing the PDU.
- Report transaction ID and unit ID as separate fields with separate meanings.

## Experiment

Mutate the MBAP length without changing the available bytes. Then change protocol ID. Explain why each failure must be caught before register interpretation.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- The unit byte is included in MBAP length.
- No RTU CRC is expected at the end.
- A split header is incomplete stream input rather than immediately malformed.

## Optional Python companion

Optionally inspect the seven header bytes with struct for an independent field comparison.

## Stretch and reflection

Why might a unit ID matter even when the IP address already identifies the TCP peer?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-10) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 63](day63.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 65](day65.md)
