# Day 97 — WAP bring-up and recovery

[Previous: Day 96](day96.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 98](day98.md)

**Week 14 · 45–90 minutes.** Prerequisites: Days 1–96, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Join real clients and make the portable lab recover predictably.

## Before you start

Dedicated Pi lab or the explicitly labeled VM/offline alternative. Hardware results must come from the actual hardware. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day97/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A working hotspot involves radio mode, regulatory settings, authentication, addressing and forwarding. A saved profile is not proof of successful association. Recovery includes reboot, uplink loss and adapter removal. Keep management reachable through a known recovery path before changing client-side networking. Your Rust health reporter observes the system; it should not silently reconfigure unrelated interfaces.

## Tiny example

Follow the chosen [NetworkManager lab recipe](TOPOLOGIES.md#pi-pocket-router) only after matching its assumptions to the actual Pi. Use a unique local credential; the course does not provide a shared default password.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Bring up one isolated WAP or wired LAN using the selected OS-supported manager and connect two clients.
- Deploy a bounded Rust health report showing interface/link status, service reachability and last successful probe; state what each field actually measures.
- Document startup, stop, reboot recovery and rollback, including how to reconnect if the LAN profile fails.

## Experiment

Disconnect the uplink while keeping the LAN powered. Verify clients can still reach the Pi locally and that the reporter distinguishes local service from upstream service.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Two clients have observed association/link and lease evidence.
- Health checks are bounded and do not infer internet availability solely from link-up.
- Rollback preserves a viable management path.

## Optional Python companion

Optional laptop client for probe comparison; the reporter is Rust.

## Stretch and reflection

How would a second radio or USB NIC simplify an unreliable single-radio design?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-14) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 96](day96.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 98](day98.md)
