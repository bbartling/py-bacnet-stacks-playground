# Day 21 — Ownership and borrowing through a real tool

[Previous: Day 20](day20.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 22](day22.md)

**Week 3 · 45–90 minutes.** Prerequisites: Days 1–20, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Explain who owns your report input and remove unnecessary copying from one data path.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day21/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A move transfers responsibility for an owned value; a borrow temporarily lets other code use it. Multiple immutable borrows are allowed, while a mutable borrow requires exclusive access for its active lifetime. Borrowing is not just a performance trick: it states who may change a buffer while another operation uses it. Cloning to silence every diagnostic hides these relationships.

## Tiny example

```rust
fn main() {
    let name = String::from("bench");
    let view = name.as_str();
    println!("{view}: {} bytes", name.len());
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Sketch ownership for the file contents, parsed readings and report in your Day 20 tool.
- Change one read-only helper to accept a borrowed view instead of consuming or cloning its input.
- Demonstrate a move error in a disposable scratch file, then choose borrowing or an intentional clone and justify it.

## Experiment

Try mutating an owned string while a borrowed slice is still needed later. Move the last use of the slice and observe how the compiler evaluates the borrow lifetime.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- You can identify the buffer owner at every function boundary.
- The caller still uses the input after a read-only operation.
- Any remaining clone has a reason beyond making compilation succeed.

## Optional Python companion

Compare two Python names referring to the same list with Rust ownership. Explain why the analogy is incomplete.

## Stretch and reflection

Where would ownership need to change if a background task outlived the function that created the input?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-3) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 20](day20.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 22](day22.md)
