# Day 32 — IPv6 addresses and interface scope

[Previous: Day 31](day31.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 33](day33.md)

**Week 5 · 45–90 minutes.** Prerequisites: Days 1–31, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Parse IPv6 endpoints correctly and explain why link-local addresses need interface context.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day32/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

IPv6 addresses have 128 bits, abbreviated with hexadecimal groups and optional zero compression. A socket endpoint brackets the address before its port. Link-local addresses are meaningful on a particular link; a scope ID identifies the interface when required. IPv6 has multicast but no broadcast. Do not assume every address beginning with a particular visual pattern is usable without checking its actual prefix.

## Tiny example

```rust
fn main() {
    use std::net::SocketAddr;
    let endpoint: SocketAddr = "[::1]:40000".parse().expect("literal endpoint");
    println!("{endpoint}, ipv6={}", endpoint.is_ipv6());
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Extend your endpoint tool with IPv6 literals and standard formatting. Keep IP-address parsing separate from socket-address parsing.
- Classify loopback, unspecified, link-local and ULA examples; include documentation prefix 2001:db8::/32 in offline tests.
- Represent scope explicitly. Standard Rust numeric parsing does not universally resolve interface names in zone syntax; inspect the platform or accept a numeric scope via SocketAddrV6.

## Experiment

Compare `::1`, `[::1]:40000`, and a link-local address with and without a scope. Use `ip -6 address` to identify actual interface-local addresses without assuming interface numbers.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- A bare IPv6 address is not parsed by splitting on colon.
- Equivalent compressed forms normalize consistently.
- Scope is preserved in a link-local endpoint representation.

## Optional Python companion

Compare canonical address formatting with ipaddress; note that address parsing and connecting are different operations.

## Stretch and reflection

Why can the same link-local address exist on two interfaces without identifying the same endpoint?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-5) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 31](day31.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 33](day33.md)
