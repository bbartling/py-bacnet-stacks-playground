# Day 95 — DNS service, local names and port ownership

[Previous: Day 94](day94.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 96](day96.md)

**Week 14 · 45–90 minutes.** Prerequisites: Days 1–94, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Prove that a leased address and working name resolution are separate outcomes.

## Before you start

Dedicated Pi lab or the explicitly labeled VM/offline alternative. Hardware results must come from the actual hardware. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day95/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A DHCP lease can advertise DNS settings without proving that the DNS service responds. A forwarding/cache service has upstream and local-name policies, and a host can already have another listener on port 53. A network manager may start an internal helper; independently launching another dnsmasq can create conflicts. Use one deliberate owner for each service/interface.

## Tiny example

Inspect `ss -lunp` and your chosen manager status before enabling another service. Record the DHCP-advertised DNS address and test that address explicitly, rather than accidentally using the laptop’s existing resolver.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Extend the Rust DNS client/report to query the lab-provided resolver with a bounded deadline.
- Test one upstream name and one local name if configured; report unsupported local-name behavior explicitly.
- Record who owns DHCP, DNS and the LAN interface. Avoid installing a second competing manager just to match a tutorial.

## Experiment

In the disposable lab, stop or misconfigure only the DNS path while leaving DHCP active. Show that the client retains an address yet name resolution fails.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Lease success and DNS query success are separate fields.
- The queried DNS endpoint is visible.
- Port conflicts or missing service ownership are diagnosed before adding another daemon.

## Optional Python companion

Optional system resolver comparison helps reveal accidental use of a different DNS server.

## Stretch and reflection

How can a cached answer hide an upstream DNS failure?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-14) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 94](day94.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 96](day96.md)
