# Day 03 — Strings, labels and bytes

[Previous: Day 2](day02.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 4](day04.md)

**Week 1 · 45–90 minutes.** Prerequisites: Days 1–2, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Build useful diagnostic labels while recognizing that Rust strings are UTF-8, not arbitrary packet buffers.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day03/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

`&str` is a borrowed view of UTF-8 text; `String` owns growable UTF-8 text. For now, use literals and formatting without mastering lifetimes. A string length counts bytes, not user-perceived characters. IP addresses represented as text are labels until parsed. Packet bytes may not be valid UTF-8 at all; that distinction becomes crucial when writing codecs.

## Tiny example

```rust
fn main() {
    let label = "pump-β";
    println!("{label}: {} bytes, {} scalar values", label.len(), label.chars().count());
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Create a status line from a device label, interface label and textual address using formatting. Do not open a socket.
- Print byte length and character count for an ASCII label and a label containing a non-ASCII character.
- Keep the original values available after building the status line; explain what owns the formatted output.

## Experiment

Try treating a string like an array with numeric indexing and read the compiler response. Explore `.chars()` instead. Do not use byte slicing on an unknown character boundary.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- The non-ASCII label prints correctly.
- Byte count and character count are not assumed equal.
- You can explain why a future packet buffer will use bytes rather than String.

## Optional Python companion

Compare `len(label)` with `len(label.encode("utf-8"))` for the same label.

## Stretch and reflection

Consider combining characters: why is `.chars().count()` still not a complete count of visible symbols?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-1) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 2](day02.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 4](day04.md)
