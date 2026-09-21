# Day 33 — IPv6 neighbors, RA and dual-stack sockets

[Previous: Day 32](day32.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 34](day34.md)

**Week 5 · 45–90 minutes.** Prerequisites: Days 1–32, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Distinguish neighbor discovery, address configuration and default-router discovery.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day33/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

IPv6 uses ICMPv6 for Neighbor Discovery, including neighbor solicitation/advertisement and router solicitation/advertisement. SLAAC uses advertised prefix information for address configuration. DHCPv6 can supply addresses or other configuration depending on deployment, but default-router discovery comes from RA. A socket bound to `::` does not have identical IPv4 behavior on every OS; configure and test the intended behavior rather than assuming it.

## Tiny example

Inspect `ip -6 route` and `ip -6 neigh`. In Wireshark, start with `icmpv6`; identify the message type from the details pane rather than guessing from a port number.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Write a Rust formatter for an IPv6 lab observation containing address, interface scope and provenance: manual, observed RA or unknown. Do not invent provenance from address shape alone.
- Create separate loopback IPv4 and IPv6 listener experiments with an existing socket tool, recording which clients connect.
- Draw separate flows for neighbor lookup, obtaining an address and learning a default router.

## Experiment

Use an isolated IPv6-capable segment or a recorded trace to identify one Neighbor Solicitation/Advertisement exchange. RA may be absent on loopback; mark the RA exercise fixture-only when needed.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- The default route is not attributed to a DHCPv6 gateway option.
- IPv6 multicast is not called broadcast.
- The report states actual bind behavior and platform.

## Optional Python companion

Optionally use two Python loopback peers to probe IPv4 and IPv6 separately.

## Stretch and reflection

Explain why indiscriminately blocking ICMPv6 can break much more than ping.

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-5) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 32](day32.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 34](day34.md)
