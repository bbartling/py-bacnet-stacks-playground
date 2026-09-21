# Day 40 — Transport headers and checksum evidence

[Previous: Day 39](day39.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 41](day41.md)

**Week 6 · 45–90 minutes.** Prerequisites: Days 1–39, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Read UDP/TCP headers only after the IP layer has established a valid boundary.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day40/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

UDP includes source/destination ports, length and checksum. TCP includes sequence state, flags, window and a data-offset field that can include options. Transport checksums include an IP pseudo-header. Host checksum offload can make an outgoing capture appear invalid before the NIC finishes the packet. A zero UDP checksum has different rules in IPv4 and IPv6; it is not a universal disabled marker.

## Tiny example

Compare a UDP length of 12 with its eight-byte header: only four bytes remain as payload. This is a field-reading exercise, not a guarantee that the IP packet is unfragmented or fully captured.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Add UDP and basic TCP header views to your inspector; require unfragmented, complete IP input for this baseline.
- Validate UDP length and TCP data offset before exposing payload. Report options as raw bounded bytes unless supported.
- Implement or independently verify one pseudo-header checksum fixture; distinguish invalid, omitted-under-IPv4-rules and not-verifiable evidence.

## Experiment

Compare the synthetic offline fixture with a live outgoing capture if available. Investigate offload before blaming the sender for a checksum discrepancy.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- A short TCP header or impossible data offset is rejected.
- UDP length includes its header.
- Output states when checksum validation was skipped and why.

## Optional Python companion

Use struct to inspect selected header fields as an independent comparison.

## Stretch and reflection

Why should a fragmented IP packet not be fed directly to your complete transport-checksum routine?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-6) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 39](day39.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 41](day41.md)
