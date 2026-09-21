# Day 39 — IPv6 headers and bounded extension walking

[Previous: Day 38](day38.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 40](day40.md)

**Week 6 · 45–90 minutes.** Prerequisites: Days 1–38, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Decode the IPv6 base header and walk a small, explicitly supported extension subset.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day39/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

The IPv6 base header is 40 bytes. Next Header identifies either an upper-layer protocol or another extension. Different extensions have different length rules, so a single universal formula is wrong. IPv6 has no base-header checksum. A robust educational parser limits both extension count and bytes inspected, reports unsupported types, and does not claim support for jumbograms or encrypted payloads.

## Tiny example

```text
base header -> optional extension -> optional extension -> upper-layer payload
Next Header chooses the next interpretation; packet length bounds every step.
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Decode version, payload length, Next Header, hop limit and source/destination addresses.
- Support a maximum of eight Hop-by-Hop or Destination Options headers using their defined length units; recognize Fragment separately and report it for later analysis.
- Report unsupported extensions and payload-length-zero jumbo cases explicitly. Never scan indefinitely looking for TCP.

## Experiment

Test a plain UDP packet, a supported options header, a truncated extension and an over-limit chain. The provided simple IPv6 fixture is a starting point; synthesize labeled mutations.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Total expected size is base-header size plus ordinary payload length.
- Hop limit is not called TTL in the output.
- Unsupported chains do not produce invented transport ports.

## Optional Python companion

Compare only addresses and lengths with a known parser or Wireshark.

## Stretch and reflection

Why can dropping all extension-bearing packets be an incomplete general-purpose network policy even if your teaching decoder rejects them?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-6) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 38](day38.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 40](day40.md)
