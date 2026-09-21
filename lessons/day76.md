# Day 76 — ReadProperty end to end

[Previous: Day 75](day75.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 77](day77.md)

**Week 11 · 45–90 minutes.** Prerequisites: Days 1–75, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Follow one confirmed BACnet transaction from request to its actual outcome.

## Before you start

Offline fixtures first; isolated BACnet peers for live evidence. No occupied building network. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day76/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A confirmed request carries an invoke ID and expects a service-appropriate response or failure. ReadProperty success normally returns a ComplexACK carrying data; SimpleACK is used by other confirmed services. Error, Reject, Abort, timeout and transport failure mean different things. A router forwarding an NPDU is not the application server answering the property read.

## Tiny example

Choose a read-only Device property exposed by your simulator, such as object-name. Record the peer address, device instance, object identifier, property identifier and invoke ID as separate facts.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Use pinned rusty-bacnet public APIs for a bounded read-only property request.
- Produce a structured result distinguishing success value, protocol failure and local timeout/transport error.
- Correlate the request and response in a capture, and compare the decoded value with an independent endpoint/client.

## Experiment

Request a supported property, an unsupported property and an unreachable lab peer. Do not force all failures into the same generic error label.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Successful ReadProperty is associated with its matching ComplexACK.
- The same invoke ID on another peer cannot be mistaken for this transaction.
- Timeout evidence includes the configured budget.

## Optional Python companion

Optionally issue the same read using bacpypes3 for comparison, without moving the Rust implementation into Python.

## Stretch and reflection

How would a late response after timeout be handled without corrupting a later transaction?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-11) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 75](day75.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 77](day77.md)
