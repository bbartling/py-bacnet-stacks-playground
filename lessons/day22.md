# Day 22 — Structs, enums and meaningful states

[Previous: Day 21](day21.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 23](day23.md)

**Week 4 · 45–90 minutes.** Prerequisites: Days 1–21, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Model endpoint configuration and parse outcomes without scattered flags.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day22/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A struct groups related fields; an enum expresses alternatives that cannot all hold at once. A result enum can prevent combinations such as both successful and invalid. Types do not automatically validate field ranges, so constructors or parsing boundaries still matter. Avoid creating a general building ontology: these types describe protocol configuration and program state.

## Tiny example

```rust
fn main() {
    enum LinkState { Down, Up { speed_mbps: u32 } }
    let state = LinkState::Up { speed_mbps: 100 };
    let _offline = LinkState::Down;
    match state {
        LinkState::Down => println!("down"),
        LinkState::Up { speed_mbps } => println!("{speed_mbps} Mb/s"),
    }
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Define an endpoint configuration with a label, parsed socket address and transport choice. Use standard address types rather than manual IP validation.
- Represent parse success and failure deliberately; include a field-specific diagnostic.
- Provide a display operation through impl or a method without opening a socket.

## Experiment

Try an unknown transport name, port overflow, a missing field and a valid bracketed IPv6 endpoint. Decide where each error belongs.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Unknown transport cannot masquerade as UDP.
- Malformed addresses never enter the valid configuration collection.
- Output includes enough context to identify the endpoint.

## Optional Python companion

Generate three configuration cases as ordinary dictionaries for Rust to consume later.

## Stretch and reflection

Which invariants can private fields and a constructor enforce?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-4) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 21](day21.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 23](day23.md)
