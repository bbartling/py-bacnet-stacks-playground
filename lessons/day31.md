# Day 31 — Routes, next hops and ARP

[Previous: Day 30](day30.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 32](day32.md)

**Week 5 · 45–90 minutes.** Prerequisites: Days 1–30, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Predict the chosen route and next-hop address before reading a capture.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day31/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

IP routing chooses a next hop; Ethernet delivery uses a local destination MAC. A remote destination IP normally remains the final host even while the frame destination is a gateway. Longest-prefix selection chooses among matching routes, followed by relevant policy and metrics. ARP resolves IPv4 neighbors on a link; it does not resolve the MAC of every remote host on the internet.

## Tiny example

```text
192.0.2.0/24  -> on-link
198.51.100.0/24 -> gateway 192.0.2.1
0.0.0.0/0 -> gateway 192.0.2.254
```
This is a teaching table; do not install it on your workstation.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Write an offline Rust longest-prefix selector for a small route table. For equal prefixes, use a documented metric/tie policy.
- Return selected prefix and next hop separately from the final destination.
- Inspect `ip route get <lab-ip>` and `ip neigh` on your actual machine; compare with your simplified model and note omitted policy routing.

## Experiment

Observe a same-link and routed exchange in the isolated lab. Display filter: `arp or icmp`. If a neighbor is already cached, explain the absence of a new ARP exchange rather than treating it as a failure.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- A more-specific route wins over a default route.
- No matching route is explicit.
- The report distinguishes gateway IP, destination IP and link-layer destination.

## Optional Python companion

Generate route-test inputs with ipaddress; implement the primary selector in Rust.

## Stretch and reflection

What changes with two route tables and policy rules? State why your model does not implement that yet.

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-5) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 30](day30.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 32](day32.md)
