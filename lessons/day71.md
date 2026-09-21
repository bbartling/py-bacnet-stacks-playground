# Day 71 — BACnet identities and the wire stack

[Previous: Day 70](day70.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 72](day72.md)

**Week 11 · 45–90 minutes.** Prerequisites: Days 1–70, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Identify each address and protocol boundary in one BACnet/IP exchange.

## Before you start

Offline fixtures first; isolated BACnet peers for live evidence. No occupied building network. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day71/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A BACnet device instance identifies an application device; an object identifier selects an object within it. An IP endpoint tells a transport where to send. A BACnet network number and MAC/address describe network-layer delivery, and those addresses depend on the data link. BVLL carries BACnet network data over IP; NPDU carries network information; APDU carries application-service information. Network messages need not contain an APDU.

## Tiny example

```text
Ethernet -> IPv4 -> UDP -> BVLC -> NPDU -> APDU -> service parameters
                                      +-> network-layer message instead
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Build a Rust observation/report type with distinct fields for transport endpoint, BACnet network address and device instance.
- Annotate the supplied unconfirmed discovery fixture from bytes to service choice.
- Document which identities are absent from a particular packet instead of filling them from a guessed device record.

## Experiment

Compare a Who-Is request and an I-Am response from an isolated peer or fixture. Identify which one advertises the device instance and which scope information is merely transport context.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Port, device instance and network number are never used interchangeably.
- The NPDU/APDU boundary is visible.
- Unknown identity stays unknown.

## Optional Python companion

Optionally use bacpypes3 as an external lab peer; it does not become the Rust program implementation.

## Stretch and reflection

Why could two different physical devices claiming the same instance break discovery even with unique IP addresses?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-11) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 70](day70.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 72](day72.md)
