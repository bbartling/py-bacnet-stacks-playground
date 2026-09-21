# Day 54 — TCP flow, retransmission and observation limits

[Previous: Day 53](day53.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 55](day55.md)

**Week 8 · 45–90 minutes.** Prerequisites: Days 1–53, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Use packet evidence to reason about stream delivery without overclaiming the cause of delays.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day54/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

Sequence and acknowledgement numbers describe byte positions, not application message numbers. Receive windows provide flow control; congestion control responds to conditions along the path. Retransmission can have several causes, and a single capture may miss packets or show offload artifacts. A slow reader can eventually reduce the advertised window. Nagle and delayed ACK behavior can influence latency but are not framing mechanisms.

## Tiny example

In Wireshark inspect a single `tcp.stream == N` after selecting its actual stream number. Sequence-analysis labels are analysis hints, not a proof that your program lost application data.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Build a bounded Rust sender/receiver experiment with a fixed total byte count and configurable receiver delay.
- Report elapsed time, bytes accepted by the application, and bytes read, without interpreting a successful write as proof of remote processing.
- Compare normal and slow-reader runs using a small capture; cap total bytes and runtime.

## Experiment

Vary only receiver pacing. If the test never fills enough buffers to expose window effects, record that limitation rather than invent a zero-window event.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Application byte totals match for successful runs.
- Retransmissions are not counted as duplicate application bytes.
- The explanation separates receive-window flow control from congestion control.

## Optional Python companion

Optionally analyze recorded timing CSV with Python; networking remains Rust.

## Stretch and reflection

What additional capture point would help distinguish sender behavior from capture loss?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-8) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 53](day53.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 55](day55.md)
