# Day 05 — Terminal input and useful output

[Previous: Day 4](day04.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 6](day06.md)

**Week 1 · 45–90 minutes.** Prerequisites: Days 1–4, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Read one line, parse an integer, and produce distinct success and error messages.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day05/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

Terminal input arrives as text, usually including a newline. Trimming and numeric parsing are separate operations. `parse::<u16>()` returns a `Result`: either a value or information about failure. A `match` chooses behavior for each case. This is a first encounter with errors; Day 18 revisits them in depth. Standard output is for results, standard error for diagnostics.

## Tiny example

```rust
fn main() {
    let input = " 27\n";
    match input.trim().parse::<u16>() {
        Ok(value) => println!("count={value}"),
        Err(error) => eprintln!("invalid count: {error}"),
    }
}
```

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Prompt for a listener port using `std::io::stdin().read_line`; handle read failure with a diagnostic.
- Parse the line as a number, apply Day 4 policy, and print either a labeled accepted value or a reason for rejection. No sockets yet.
- Accept surrounding whitespace; reject empty, negative, oversized and alphabetic values without panicking.

## Experiment

Type a valid value, a word, and a blank line in separate runs. Redirect stdout to a file while leaving stderr visible; observe which messages go where.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Newlines do not make valid input fail.
- Invalid input does not reach the accepted-output path.
- Read failure and invalid numeric text are distinguishable in your code.

## Optional Python companion

Use `input()` and catch numeric conversion failure. Compare newline handling with Rust read_line.

## Stretch and reflection

Add a meaningful nonzero process exit status for invalid input. Why should automation care about the exit status?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-1) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 4](day04.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 6](day06.md)
