# Day 65 — A read-only Modbus register client

[Previous: Day 64](day64.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 66](day66.md)

**Week 10 · 45–90 minutes.** Prerequisites: Days 1–64, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Implement a narrow register-read transaction with validated responses.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day65/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

Function 03 reads holding registers; its wire address is a zero-based protocol address, not necessarily the same text displayed in vendor manuals. Request quantity, response byte count, unit ID, function and transaction ID all need validation. Exception responses are legitimate protocol outcomes with an exception function code and exception code; they are not malformed packets merely because no data arrived.

## Tiny example

A request for two registers should return four data bytes in a normal function-03 response. A server exception is a different response shape and must not be parsed as those four data bytes.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Build a Rust function-03 client for an explicitly configured simulator endpoint, starting address and quantity 1..=125.
- Reject a range that exceeds the address space; validate response correlation and exact byte count.
- Use a bounded transaction deadline and report normal, exception, malformed and timeout results separately.

## Experiment

Read two known simulator registers, request an unsupported address and stop the simulator. Compare the three outcomes in the capture.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Known raw register words match the independent simulator definition.
- Exception response is decoded rather than mislabeled as timeout.
- Oversized quantity is rejected before transmission.

## Optional Python companion

Optionally use a maintained Python simulator or client as the independent side; implement the learning client in Rust.

## Stretch and reflection

Why is a successful TCP write insufficient evidence that a Modbus write took effect?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-10) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 64](day64.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 66](day66.md)
