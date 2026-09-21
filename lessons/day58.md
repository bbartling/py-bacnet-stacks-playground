# Day 58 — Shared state and backpressure

[Previous: Day 57](day57.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 59](day59.md)

**Week 9 · 45–90 minutes.** Prerequisites: Days 1–57, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Choose explicit limits for tasks, queues and shared data.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day58/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

Arc shares ownership, not automatic safe mutation. Mutexes provide exclusive access, but holding one across slow I/O can serialize unrelated tasks. A bounded channel creates a place where overload must be addressed: wait, reject, coalesce or drop according to the meaning of the message. An unbounded task count can defeat an otherwise bounded queue.

## Tiny example

Compare two policies for metrics: retain every event, or periodically publish the newest aggregate. The latter can be appropriate for a dashboard; dropping a protocol response under the same rule may be incorrect.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Add a bounded status channel of capacity eight between a Rust producer and consumer. Document the full-queue policy.
- Use shared state only for a small counter/config snapshot; keep network I/O outside its critical section.
- Limit task admission separately and expose active/queued/rejected counts.

## Experiment

Slow the consumer deliberately and drive a finite burst larger than the queue. Check whether measured behavior matches the chosen policy.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Queue length is bounded and overload is observable.
- Protocol work is not silently treated like disposable metrics.
- Lock scope does not include a slow socket operation.

## Optional Python companion

Optionally plot the saved queue-depth log; the concurrency implementation stays Rust.

## Stretch and reflection

Can a bounded channel still allow unlimited memory elsewhere? Identify two examples.

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-9) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 57](day57.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 59](day59.md)
