# Day 43 — UDP sockets and datagram boundaries

[Previous: Day 42](day42.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 44](day44.md)

**Week 7 · 45–90 minutes.** Prerequisites: Days 1–42, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Build a small Rust UDP exchange while preserving one-message-per-datagram behavior.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day43/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A UDP bind chooses a local address and port. Binding to loopback restricts the experiment to the host. A receive returns one datagram and its source, but an undersized buffer may discard excess bytes depending on the platform. A timeout is an I/O outcome, not an empty message. A zero-length datagram is a legitimate transport event unless the application forbids it.

## Tiny example

```rust
fn main() {
    use std::net::UdpSocket;
    let socket = UdpSocket::bind("127.0.0.1:0").expect("loopback bind");
    println!("assigned endpoint={}", socket.local_addr().expect("local address"));
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Create Rust sender and responder modes on loopback, echoing opaque payloads up to 256 bytes with a two-second receive deadline.
- Receive into a buffer larger than the application maximum and reject oversized results; do not mistake a full small buffer for proof of a complete datagram.
- Print the peer endpoint and exact byte count; no UTF-8 assumption. Bound the responder by message count or duration.

## Experiment

Send a short payload, an empty payload and one exceeding the application limit. Then stop the responder and observe timeout behavior. Filter: `udp.port == 40000` if that is your chosen fixed port.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Reply bytes exactly match accepted input.
- Oversize and timeout are separate outcomes.
- No daemon is left running after the bounded experiment.

## Optional Python companion

Optionally use socket.sendto/recvfrom as an independent peer; otherwise run two Rust processes.

## Stretch and reflection

What does UDP connect change, and why does it not create a TCP-style handshake?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-7) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 42](day42.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 44](day44.md)
