# Day 87 — Trace an NPDU across a router

[Previous: Day 86](day86.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 88](day88.md)

**Week 13 · 45–90 minutes.** Prerequisites: Days 1–86, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Follow directed BACnet traffic through two distinct BACnet networks.

## Before you start

Offline fixtures first; isolated BACnet peers for live evidence. No occupied building network. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day87/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A BACnet router changes link encapsulation and network-layer routing information as required while preserving the application service. BACnet source/destination addressing and hop count differ from IP source/destination and TTL. Same-host sockets on different UDP ports are useful functional tests but do not prove physical interface binding or broadcast behavior; state exactly which topology is used.

## Tiny example

```text
application client -- BACnet network 1001 -- router -- BACnet network 2001 -- device
IP addresses and prefixes are labeled separately underneath each link.
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Use pinned stack public routing APIs or the destination repo dual-B/IP harness in the isolated topology; do not implement the appliance forwarder from scratch.
- Send one directed read-only request through the router and capture both sides.
- Write a Rust comparison tool or report that identifies preserved APDU bytes and changed link/network fields.

## Experiment

Remove the destination route in the disposable test configuration and repeat. Explain whether the observed failure is local, network-layer or application timeout.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- The request actually traverses two BACnet networks, not just two labels on one direct connection.
- APDU identity is preserved for the correlated transaction.
- Hop count and IP TTL are reported separately.

## Optional Python companion

Optional external bacpypes3 is an oracle on a separate bind address, not part of the router data plane.

## Stretch and reflection

What would prove that a directed reply returns through the intended router rather than a parallel path?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-13) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 86](day86.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 88](day88.md)
