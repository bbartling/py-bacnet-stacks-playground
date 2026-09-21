# Day 50 — TCP connections and a bounded server

[Previous: Day 49](day49.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 51](day51.md)

**Week 8 · 45–90 minutes.** Prerequisites: Days 1–49, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Accept a TCP connection and explain its lifecycle using a capture.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day50/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

TCP provides an ordered byte stream between endpoints. Listening creates a socket ready for incoming connections; accepting creates a separate connected stream. A successful connect is not proof that the application protocol is healthy. Local refusal, routing failure and silent dropping can produce different outcomes and timing. Begin with loopback and one bounded connection.

## Tiny example

Observe `ss -ltn` before and after starting your listener. In Wireshark, use `tcp.port == 40001` for the chosen lab port and inspect SYN, SYN/ACK and ACK flags.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Write Rust listener and client modes using std::net, with explicit loopback address and a connect deadline.
- Exchange a fixed short greeting and close after one connection; set read/write timeouts.
- Report local and peer addresses from the connected stream, not merely the requested target string.

## Experiment

Connect before the server starts, during its run, and after it exits. Capture one success and record the distinct failed outcomes.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Listener and accepted stream are described separately.
- The server exits without an orphaned background process.
- The report does not equate handshake success with arbitrary service readiness.

## Optional Python companion

Optionally use socket.create_connection as an independent client.

## Stretch and reflection

Why can two connections share a server port while still being distinct?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-8) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 49](day49.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 51](day51.md)
