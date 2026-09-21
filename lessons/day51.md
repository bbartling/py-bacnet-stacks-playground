# Day 51 — Partial reads and writes are normal

[Previous: Day 50](day50.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 52](day52.md)

**Week 8 · 45–90 minutes.** Prerequisites: Days 1–50, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Make application behavior independent of how TCP bytes are chunked.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day51/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

TCP does not preserve send-call boundaries. One write can arrive through multiple reads, and several writes can appear in one read. Read returns what is available within its contract; Write can consume less than the entire supplied buffer. A packet capture observes segments, while the application reads a reassembled stream. Tests must vary input chunk boundaries instead of relying on localhost luck.

## Tiny example

```text
Same byte stream:  a b c d e f
Possible reads:   [a b] [c d e f]
Also possible:    [a] [b] [c] [d e] [f]
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Write a Rust stream consumer that collects an explicitly fixed six-byte teaching record before reporting it, with a size and time bound.
- Test it using a Read test double that returns at most one or two bytes per call.
- Exercise a partial Write test double or write_all behavior; preserve the difference between clean EOF and EOF before six bytes.

## Experiment

Have a peer write the record in separate pieces with short delays. Compare with one write and with immediate close halfway through.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- All complete chunkings produce identical record bytes.
- Premature EOF is not a valid shorter record.
- No assertion assumes a particular recv/read chunk size on a live socket.

## Optional Python companion

Optionally send the same record using several sendall calls, while recognizing that this does not guarantee matching receive boundaries.

## Stretch and reflection

Why does TCP_NODELAY still not create application message boundaries?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-8) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 50](day50.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 52](day52.md)
