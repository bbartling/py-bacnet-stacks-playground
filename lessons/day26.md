# Day 26 — A command-line contract people can use

[Previous: Day 25](day25.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 27](day27.md)

**Week 4 · 45–90 minutes.** Prerequisites: Days 1–25, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Design arguments, configuration and exit behavior that can be driven by another program.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day26/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A CLI is an API. Help text should state input format, defaults and units. `clap` can validate syntax and produce usage text, but your application must still validate semantic relationships. Separate machine-readable output from diagnostics. Dependencies belong in Cargo.toml and a committed lockfile; record the exact version selected rather than relying on a tutorial screenshot.

## Tiny example

For a scratch package, inspect `cargo add clap --features derive` and the current clap derive tutorial. A sample command shape is `fieldtool inspect --input sample.bin --max-bytes 1024`; this describes the interface, not its implementation.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Add `--input`, `--max-bytes` and a report-format option to one earlier tool. Provide `--help`.
- Reject a missing file path, an invalid limit and an unsupported output format before processing data.
- Keep successful machine output on stdout and diagnostics on stderr; publish an exit-code policy.

## Experiment

Pipe successful output to a file, then repeat with invalid arguments. Verify that the file is not contaminated by prompts or a stack trace.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Help includes units and the default limit.
- Argument errors and processing errors are identifiable.
- The selected dependency version and Cargo.lock are recorded.

## Optional Python companion

Use subprocess to run the Rust binary and inspect returncode, stdout and stderr separately.

## Stretch and reflection

When should CLI options override file configuration, and how would you make that precedence visible?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-4) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 25](day25.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 27](day27.md)
