# Day 85 — A disposable two-network laboratory

[Previous: Day 84](day84.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 86](day86.md)

**Week 13 · 45–90 minutes.** Prerequisites: Days 1–84, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Create an isolated topology whose routes and broadcast boundaries you can explain.

## Before you start

Offline fixtures first; isolated BACnet peers for live evidence. No occupied building network. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day85/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A Linux network namespace has its own network stack view. A veth pair joins two interfaces as a virtual link; a bridge joins a link-layer domain. These tools let one computer model multiple hosts, but do not reproduce electrical serial timing or Wi-Fi radio behavior. Keep host uplinks out of the topology and make cleanup part of the experiment.

## Tiny example

Use [TOPOLOGIES.md](TOPOLOGIES.md#namespace-lab) for the `client — router — server` namespace recipe. Its addresses and names are confined to disposable namespaces and are not installed on host interfaces.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Build the documented namespace topology in a disposable Linux VM, checking that the names do not already exist.
- Run your Rust endpoint tool and UDP/TCP tools on explicit interfaces inside it.
- Record interfaces, addresses, routes and processes; provide a teardown procedure that only removes resources you created.

## Experiment

Test delivery before and after enabling forwarding inside the router namespace. Observe the two links separately; do not change host forwarding.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- The host default route remains unchanged.
- The two endpoint networks have distinct prefixes.
- Cleanup removes all course-created namespace processes and interfaces after an intentional normal stop.

## Optional Python companion

Optional peers may run inside the endpoint namespaces; Rust remains the network-tool implementation.

## Stretch and reflection

Where does a bridge collapse a boundary that a router would preserve?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-13) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 84](day84.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 86](day86.md)
