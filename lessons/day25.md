# Day 25 — Read, Write and test doubles

[Previous: Day 24](day24.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 26](day26.md)

**Week 4 · 45–90 minutes.** Prerequisites: Days 1–24, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Exercise I/O logic against memory before putting it on a socket.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day25/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

Traits describe behavior shared by different concrete types. Files, memory cursors and sockets can implement Read or Write, but their runtime behavior differs. A Read call can return fewer bytes than requested; EOF is reported with zero bytes for a nonempty buffer. Generic code becomes useful when it lets you test these cases without real networking.

## Tiny example

```rust
fn main() {
    use std::io::{Cursor, Read};
    let mut source = Cursor::new(b"abc");
    let mut byte = [0_u8; 1];
    let n = source.read(&mut byte).expect("memory read");
    println!("read={n}, byte={}", byte[0]);
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Write an operation accepting a Read source that counts bytes up to an explicit limit and reports limit overflow.
- Call it with a file and with Cursor over in-memory bytes. Keep output outside the operation.
- Introduce a test source that returns small chunks or a deliberate error; do not assume one read fills a buffer.

## Experiment

Run the same bytes through one large chunk and many small chunks. Then inject failure after a known prefix and state whether partial results are returned.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Chunking does not change the successful count.
- Exactly-at-limit and one-over-limit differ.
- A source error is not treated as clean EOF.

## Optional Python companion

Use io.BytesIO to exercise equivalent input behavior.

## Stretch and reflection

What responsibilities would a Write implementation add around partial writes?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-4) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 24](day24.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 26](day26.md)
