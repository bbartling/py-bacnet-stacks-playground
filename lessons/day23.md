# Day 23 — Binary buffers and hexadecimal inspection

[Previous: Day 22](day22.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 24](day24.md)

**Week 4 · 45–90 minutes.** Prerequisites: Days 1–22, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Inspect arbitrary bytes without treating them as text or reading beyond a slice.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day23/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

An array has a fixed size, a Vec owns a growable buffer, and a slice borrows a contiguous region. Binary protocol values may contain zero and non-UTF-8 bytes. Hex is a representation of bytes, not an encoding layer on the wire unless a protocol says so. Bounds checks and explicit offsets are the foundation of a trustworthy packet decoder.

## Tiny example

```rust
fn main() {
    let raw = [0x00_u8, 0x7f, 0xff];
    for byte in raw { print!("{byte:02x} "); }
    println!();
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Read a bounded binary file and print offsets plus hexadecimal bytes in rows. Choose and document a row width.
- Show the byte count and a separate optional text preview that cannot panic on invalid UTF-8.
- Handle empty input and a final row shorter than the chosen width.

## Experiment

Use bytes containing zero, a newline and 0xff. Compare byte count with a lossy string preview and explain why the preview cannot reconstruct the original data.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Every input byte appears exactly once in hex output.
- The partial final row has correct offsets.
- The preview never changes the raw bytes used for later parsing.

## Optional Python companion

Use `bytes.hex()` as an independent formatting reference.

## Stretch and reflection

Add a maximum displayed length while retaining the true input length and an explicit truncated-preview marker.

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-4) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 22](day22.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 24](day24.md)
