# Day 93 — Plan a pocket router topology

[Previous: Day 92](day92.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 94](day94.md)

**Week 14 · 45–90 minutes.** Prerequisites: Days 1–92, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Choose real interfaces and distinguish a routed LAN from a bridge.

## Before you start

Dedicated Pi lab or the explicitly labeled VM/offline alternative. Hardware results must come from the actual hardware. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day93/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A pocket router needs a client-facing network and an uplink path. Wi-Fi AP support depends on the actual radio/driver; concurrent station/AP mode is not universal. USB Ethernet and supported USB gadget links can carry IP, while USB RS-485 adapters remain serial devices. Bridging LAN interfaces shares a broadcast domain; routing between them preserves separate domains and requires distinct address plans.

## Tiny example

Use [the Pi topology worksheet](TOPOLOGIES.md#pi-pocket-router): record uplink, LAN/AP, management recovery path, OS network manager and a non-overlapping LAN prefix before issuing configuration commands.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Write a Rust inventory formatter that consumes recorded interface name/type/address data and prints the planned roles without changing the OS.
- Verify actual AP capability with the OS tools and identify which interface is your current SSH path.
- Choose a baseline topology: Ethernet uplink plus Wi-Fi AP, or separate wired uplink/LAN with an external AP. A VM can cover routing while radio tests remain pending.

## Experiment

Unplug only a disposable lab-side adapter and observe which interface disappears. Do not assume a USB enumeration number is a stable interface identity.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- LAN prefix does not overlap uplink or VPN routes.
- A separate recovery path is documented.
- DHCP is associated with IP-capable clients, not arbitrary USB peripherals.

## Optional Python companion

Optional: normalize a saved interface inventory for comparison; Rust remains the formatter.

## Stretch and reflection

Which Pi model/port would support USB gadget mode, and what hardware documentation proves it?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-14) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 92](day92.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 94](day94.md)
