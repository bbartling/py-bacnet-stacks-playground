# Day 46 — A small DNS wire exercise

[Previous: Day 45](day45.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 47](day47.md)

**Week 7 · 45–90 minutes.** Prerequisites: Days 1–45, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Implement a bounded DNS query/response subset and understand compressed names.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day46/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

DNS messages carry a header, question and resource-record sections. Names are sequences of length-prefixed labels; responses may use compression pointers to other offsets. Pointer jumps need bounds and loop detection. Response IDs alone are insufficient correlation: peer, question and relevant header flags also matter. This exercise supports ordinary A/AAAA queries, not a full recursive resolver.

## Tiny example

For a name such as `lab.example`, write label lengths next to the characters and a final zero-length label on paper. Compression pointers consume bytes in the original stream while their referenced names live elsewhere; track those two positions separately.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Encode one standard single-question A or AAAA query with a chosen ID, using [RFC references](SOURCES.md#week-7).
- Decode a bounded response: maximum 4096 bytes, 32 records and 16 pointer hops; enforce name/label limits and check the echoed question.
- Report DNS error codes and truncation explicitly. TCP fallback is an extension, not a silently successful partial answer.

## Experiment

Use fixture responses with an ordinary name, a valid compressed name, an out-of-range pointer and a pointer cycle. A configured lab resolver may provide an additional live comparison.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Compression loops terminate with a clear error.
- A wrong question or ID cannot satisfy the request.
- Unsupported record types can be skipped using validated record lengths.

## Optional Python companion

Optionally obtain an independent expected answer with a DNS library or system tool; Rust owns the codec.

## Stretch and reflection

After the TCP week, add length-prefixed DNS-over-TCP fallback and preserve the same overall deadline.

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-7) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 45](day45.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 47](day47.md)
