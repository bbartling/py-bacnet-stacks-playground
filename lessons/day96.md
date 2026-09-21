# Day 96 — Linux forwarding, NAT and firewall evidence

[Previous: Day 95](day95.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 97](day97.md)

**Week 14 · 45–90 minutes.** Prerequisites: Days 1–95, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Explain an actual IP-forwarding path and separate it from the Rust TCP proxy.

## Before you start

Dedicated Pi lab or the explicitly labeled VM/offline alternative. Hardware results must come from the actual hardware. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day96/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

Linux forwards packets between interfaces according to routes and policy. IPv4 masquerading rewrites source addressing for an uplink; it is not required for every routed topology. Stateful firewall behavior can allow replies without allowing arbitrary incoming connections. IPv6 normally uses routed prefixes and RA rather than copying an IPv4 NAT recipe. NetworkManager shared mode may own forwarding/NAT rules itself.

## Tiny example

Use the namespace lab for an explicit route experiment, and inspect `ip route`, `sysctl net.ipv4.ip_forward`, and `nft list ruleset` in the correct context. Observation commands do not justify flushing the host firewall.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Write a Rust report comparing a flow’s source/destination tuple on LAN and uplink captures.
- Use either NetworkManager-managed sharing or a documented manual route/firewall setup, never overlapping ownership.
- Test one allowed outbound flow and one excluded management/inbound path. State whether NAT is present.

## Experiment

Compare direct IP forwarding with traffic through the Rust proxy: the proxy creates two TCP connections, while ordinary forwarding carries the same connection subject to address translation.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Firewall/forwarding changes stay confined to the dedicated lab environment.
- NAT behavior is shown with before/after addresses.
- IPv6 is either explicitly configured and tested or explicitly disabled on the lab share—not accidentally left ambiguous.

## Optional Python companion

Optional capture analysis only; no Python packet-forwarding service is required.

## Stretch and reflection

How would you prove that a rejected inbound test actually reached the firewall rather than failed earlier?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-14) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 95](day95.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 97](day97.md)
