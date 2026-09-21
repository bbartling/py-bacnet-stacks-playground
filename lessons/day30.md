# Day 30 — IPv4 prefixes and subnet membership

[Previous: Day 29](day29.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 31](day31.md)

**Week 5 · 45–90 minutes.** Prerequisites: Days 1–29, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Calculate whether two IPv4 addresses share a prefix and verify boundary cases.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day30/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

IPv4 addresses have 32 bits. A CIDR prefix says how many leading bits identify a network; it is not a count of connected devices. Subnet membership, usable-host policy and route selection are separate questions. The familiar host-count subtraction does not apply uniformly to /31 point-to-point links or /32 host routes. Treat special-use ranges as address classifications, not proof of reachability.

## Tiny example

```rust
fn main() {
    use std::net::Ipv4Addr;
    let addr = Ipv4Addr::new(192, 0, 2, 9);
    println!("octets={:?}", addr.octets());
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Build a Rust prefix-membership function for an IPv4 address, network address and prefix length 0..=32. Normalize host bits in the supplied network before comparing.
- Report the normalized network and membership result. Reject invalid prefixes instead of shifting by an invalid count.
- Use documentation addresses such as 192.0.2.0/24 for offline tests; do not assign them to unrelated real networks.

## Experiment

Compare 192.0.2.127 and 192.0.2.128 against a /25. Add /0 and /32 cases, predicting the results first.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- /0 covers every IPv4 address.
- /32 covers exactly one address.
- Membership is not confused with broadcast/host assignment policy.

## Optional Python companion

Compare with `ipaddress.ip_network(..., strict=False)` and membership checks.

## Stretch and reflection

Add /31 test cases and explain why counting usable hosts is a separate operation.

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-5) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 29](day29.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 31](day31.md)
