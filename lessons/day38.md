# Day 38 — IPv4 headers, options and checksums

[Previous: Day 37](day37.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 39](day39.md)

**Week 6 · 45–90 minutes.** Prerequisites: Days 1–37, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Validate IPv4 header boundaries before trusting transport offsets.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day38/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

IPv4 IHL is a count of 32-bit words, so options can make the header longer than the common minimum. Total length bounds the IP packet independently of Ethernet padding. The header checksum covers the IPv4 header, not its payload. Fragment fields change whether the remaining bytes contain an entire transport message; recognize them now and defer transport decoding of fragments.

## Tiny example

Use the [IPv4/UDP fixture](fixtures/README.md): locate the first byte, derive version and IHL, and compare total length against the captured bytes. The fixture manifest identifies header checksum bytes but does not provide a parser.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Decode version, IHL, total length, TTL, protocol, addresses and fragmentation fields. Validate minimum header length and available bytes.
- Implement header-checksum verification for the declared header including options; preserve the original bytes.
- Report a truncated capture separately from an internally impossible total length. Do not treat Ethernet padding as IP payload.

## Experiment

Mutate one header byte without updating the checksum, then shorten the capture. Explain why these are two different failures.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- An IHL below the minimum is rejected.
- A total length shorter than the header is rejected.
- Options do not move the transport offset by a hard-coded 20 bytes.

## Optional Python companion

Independently calculate one known header checksum or compare against Wireshark; avoid generating both expected and actual through the same Rust function.

## Stretch and reflection

Why does changing TTL require an IPv4 header-checksum update?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-6) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 37](day37.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 39](day39.md)
