# Day 62 — Tracing a slow connection

[Previous: Day 61](day61.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 63](day63.md)

**Week 9 · 45–90 minutes.** Prerequisites: Days 1–61, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Collect useful operational evidence without making logging the bottleneck.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day62/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A connection ID links events across tasks. Aggregate counters answer how much work occurred, while structured spans help explain one session. Logs should avoid unbounded payload dumps and secrets. Performance experiments need a fixed workload and comparable environments; localhost results do not predict MS/TP timing or Wi-Fi performance. Instrumentation itself consumes CPU, memory and I/O.

## Tiny example

A compact event might contain `connection_id`, `listener`, `backend`, `outcome`, `duration_ms`, `bytes_up`, and `bytes_down`. Raw application payload is unnecessary for this metric.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Add tracing and aggregate counters to your Rust proxy. Bound or sample verbose events.
- Run a finite normal workload and a slow-backend workload with identical client counts and byte totals.
- Report active/accepted/rejected connections and final outcomes with units; distinguish accepted from completed.

## Experiment

Reduce log verbosity and repeat the same workload. Describe whether the difference is meaningful with the small sample rather than declaring a benchmark victory.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- One connection can be followed from accept to finish.
- Counters reconcile at shutdown or disclose unfinished work.
- Slow logging cannot enqueue unlimited data.

## Optional Python companion

Optionally summarize the result CSV or JSON in Python; it is an analysis helper only.

## Stretch and reflection

What resource measurement would reveal a task leak that request latency alone might miss?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-9) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 61](day61.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 63](day63.md)
