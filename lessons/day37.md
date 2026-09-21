# Day 37 — Ethernet headers and capture link types

[Previous: Day 36](day36.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 38](day38.md)

**Week 6 · 45–90 minutes.** Prerequisites: Days 1–36, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Decode a declared Ethernet subset while refusing unsupported capture encapsulation.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day37/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

An Ethernet II header contains destination MAC, source MAC and EtherType. VLAN tags add fields before the encapsulated EtherType. A PCAP record also has a capture link type and captured/original length; its bytes are not automatically Ethernet. FCS is often not present in host captures. Do not subtract a guessed checksum trailer or assume packet alignment.

## Tiny example

```text
Ethernet II: destination[6] | source[6] | EtherType[2] | payload
Single VLAN: ... | TPID[2] | TCI[2] | inner EtherType[2] | payload
```
A capture container parser supplies link type and record lengths before this decoder runs.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Implement Ethernet II parsing for untagged frames and one 802.1Q tag. Extract MACs, EtherType and optional VLAN ID.
- Reject truncated headers and report stacked tags as outside this lesson subset rather than treating their bytes as IP.
- Use the supplied synthetic Ethernet PCAP; compare one record with tcpdump or Wireshark.

## Experiment

Feed the same bytes to a harness declaring a different link type. The dispatcher should refuse the mismatch before Ethernet field interpretation.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Untagged and tagged header offsets differ correctly.
- Captured length bounds every read.
- FCS presence is not assumed.

## Optional Python companion

Use a small bytes slice only to inspect MAC fields; keep the main parser in Rust.

## Stretch and reflection

What metadata would you need to support Linux cooked captures next?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-6) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 36](day36.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 38](day38.md)
