# Day 34 — DNS, resolution and connection failures

[Previous: Day 33](day33.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 35](day35.md)

**Week 5 · 45–90 minutes.** Prerequisites: Days 1–33, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Separate a name lookup from opening a transport connection.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day34/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A resolver can consult caches, local files and DNS; resolving a name is not necessarily a new wire query. A records describe IPv4 addresses and AAAA records describe IPv6 addresses. Multiple returned addresses are candidates, not proof that all are reachable. TTL concerns cached data lifetime. Numeric endpoint validation should not unexpectedly perform DNS or contact a network.

## Tiny example

```rust
fn main() {
    use std::net::ToSocketAddrs;
    match ("localhost", 40000).to_socket_addrs() {
        Ok(addresses) => for address in addresses { println!("{address}"); },
        Err(error) => eprintln!("resolution failed: {error}"),
    }
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Build a Rust resolver-report CLI taking a hostname and port, listing returned addresses without claiming a successful connection.
- Include elapsed time and a distinct resolution-error result. State that the standard resolver call can block and has no simple portable per-call timeout setting.
- Test localhost plus an explicitly selected lab DNS name; offline runs can inject a fixed address list.

## Experiment

Compare a numeric address with a hostname. Inspect `dns` traffic only when the resolver actually emits it; a cache hit or local hosts entry may produce none.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- A resolution result is not labeled reachable.
- Multiple results are retained.
- No-response, nonexistent name and no emitted query are not conflated.

## Optional Python companion

Compare `socket.getaddrinfo` results while recording that resolver ordering can differ.

## Stretch and reflection

Where should a later async application isolate blocking resolution work?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-5) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 33](day33.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 35](day35.md)
