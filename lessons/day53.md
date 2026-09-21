# Day 53 — Half-close, EOF and connection shutdown

[Previous: Day 52](day52.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 54](day54.md)

**Week 8 · 45–90 minutes.** Prerequisites: Days 1–52, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Allow a peer to finish sending without prematurely discarding its remaining response.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day53/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A TCP connection has two directions. A write-half shutdown says no more bytes will be sent while still allowing reads. EOF on the receive direction is different from a reset and different from an application timeout. Closing both directions as soon as one reader ends can lose a valid response, especially through a proxy. Slow peers need both idle policy and total-operation bounds.

## Tiny example

```text
client sends request -> client shuts down writing
server observes EOF -> server finishes response
client continues reading -> server finishes writing
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Modify a small Rust request/response experiment so the client half-closes after its request but reads the full response.
- Give the server an explicit incomplete-frame-at-EOF error.
- Log whether termination was clean EOF, reset, timeout or local cancellation; do not infer the reason only from a generic disconnected label.

## Experiment

Use a peer that waits for request EOF before sending its response. Compare with an intentionally early full close in a scratch version.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- The valid response survives client write-half shutdown.
- Partial frames followed by EOF fail clearly.
- Timeout ends a stalled session within its declared budget.

## Optional Python companion

Optionally exercise socket.shutdown(SHUT_WR) in the test client.

## Stretch and reflection

Why must a TCP proxy propagate half-close directionally rather than cancel both forwarding tasks immediately?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-8) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 52](day52.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 54](day54.md)
