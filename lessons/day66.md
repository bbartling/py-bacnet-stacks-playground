# Day 66 — Modbus stream boundaries and transaction matching

[Previous: Day 65](day65.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 67](day67.md)

**Week 10 · 45–90 minutes.** Prerequisites: Days 1–65, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Keep a Modbus client correct under split replies, coalesced ADUs and stale IDs.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day66/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

MBAP gives an application boundary independent of TCP. The decoder must retain incomplete bytes and leave later ADUs available. A transaction identifier matches an outstanding request on a connection, but a stale reply must not complete a new request after careless reuse. Begin with one outstanding request; concurrency adds bookkeeping and is an extension.

## Tiny example

```text
read 1: first 3 MBAP bytes
read 2: remaining header + part of data
read 3: remainder + next complete ADU
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Reuse your incremental-decoder lessons for Modbus TCP framing with a documented ADU bound.
- Match transaction and unit identifiers plus function outcome; reject or quarantine an unexpected reply under a written policy.
- Use one outstanding request, an overall deadline and no immediate ID reuse within the test connection.

## Experiment

Create a test peer that sends a valid reply in several chunks and then a stale reply. Repeat with two concatenated ADUs.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Chunking does not affect decoded result.
- Unexpected replies do not reset the overall deadline.
- Disconnect mid-ADU is reported as truncation/transport failure.

## Optional Python companion

Optionally send deliberately split fixture bytes from Python to the Rust client.

## Stretch and reflection

What state and limits would be necessary to support several concurrent transaction IDs?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-10) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 65](day65.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 67](day67.md)
