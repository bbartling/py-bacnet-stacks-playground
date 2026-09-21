# Day 57 — Async Rust without changing the protocol

[Previous: Day 56](day56.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 58](day58.md)

**Week 9 · 45–90 minutes.** Prerequisites: Days 1–56, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Port a working blocking service to Tokio while preserving its observable contract.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day57/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

An async function returns a future; progress happens when a runtime polls it. Await can suspend a task so other work proceeds, but blocking calls still block the thread running them. Concurrency is not automatically CPU parallelism. Start from a protocol already tested in memory, and change the I/O boundary rather than rewrite framing and application behavior simultaneously.

## Tiny example

In a new package, add Tokio features `macros`, `rt-multi-thread`, `net`, `io-util`, `time`, `sync`, and `signal` as needed. Read the current setup tutorial and record the resolved version. Avoid enabling unrelated features simply because an old example did.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Port your Day 56 accept/client handling to Tokio, retaining the existing frame codec and size limits.
- Use async socket operations and Tokio timers; identify any remaining blocking file, DNS or CPU work.
- Retain a concurrency cap and record which task owns each stream.

## Experiment

Run the same protocol fixtures against blocking and async versions. Add two delayed clients and observe that one does not prevent the other from making progress.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Protocol output remains compatible.
- No std::thread::sleep sits in the async connection path.
- The runtime and task ownership are explained.

## Optional Python companion

Optionally reuse the same external peer to compare both implementations; no Python async rewrite is required.

## Stretch and reflection

When would spawn_blocking help, and why does it still require workload limits?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-9) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 56](day56.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 58](day58.md)
