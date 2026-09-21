# Day 94 — DHCP leases and a bounded option decoder

[Previous: Day 93](day93.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 95](day95.md)

**Week 14 · 45–90 minutes.** Prerequisites: Days 1–93, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Observe DHCPv4 address assignment and decode selected fields in Rust.

## Before you start

Dedicated Pi lab or the explicitly labeled VM/offline alternative. Hardware results must come from the actual hardware. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day94/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

DHCPv4 builds on a fixed message structure plus a cookie and options. Options are type/length/value except special pad/end forms. Transaction ID and client identity correlate an exchange; source IP may be zero before configuration. Initial DORA and later renewal are different flows. A general-purpose daemon should serve the real LAN while your Rust work inspects and diagnoses it.

## Tiny example

Use [the synthetic DHCP fixture](fixtures/dhcp/README.md) to locate the transaction ID, hardware length, client hardware address, magic cookie and message-type option. The fixture is not a recorded lease or proof of a DHCP server.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Build a Rust decoder for the fixed DHCPv4 header and options 53, 50, 51, 54, 1, 3 and 6, with a 1500-byte input bound.
- Handle pad/end safely, validate each known option length and report unsupported option-overload instead of silently pretending full support.
- Observe a lease from the selected network manager/daemon on the isolated LAN; no custom DHCP server is required.

## Experiment

Compare a Discover and Offer/Ack where available, then truncate an option body in the offline fixture. Filter: `udp.port == 67 or udp.port == 68`.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- A missing or bad cookie is rejected.
- Option bounds and hardware-address length are checked.
- A synthetic packet is not described as a successful live lease.

## Optional Python companion

Optional struct-based field inspection is an independent comparator.

## Stretch and reflection

Why may a renewal be unicast even though initial discovery used broadcast?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-14) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 93](day93.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 95](day95.md)
