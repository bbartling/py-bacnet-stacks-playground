# Day 01 — Set up a Rust networking workbench

[Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 2](day02.md)

**Week 1 · 45–90 minutes.** Prerequisites: No programming prerequisite; a terminal and editor.

## Goal

Build and run a tiny Rust executable, make an intentional compiler error, and distinguish source, build output, and terminal output.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day01/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

Cargo manages packages, dependencies, builds and tests. rustc is the compiler underneath it. A package can contain a binary and a library; today only a binary is needed. Rust catches many mistakes before execution, but a successful build does not prove that a program behaves correctly. Python will later act as an independent network peer. Neither language needs access to a BACnet device today.

## Tiny example

Create a disposable package with `cargo new hello_wire --bin`, enter it, and run `cargo run`. Change the greeting, then remove one closing quote and read the compiler diagnostic. Restore it. `cargo --version`, `rustc --version`, and `python3 --version` identify the tools actually used.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Install Rust through the official rustup instructions if missing. Python is optional for comparison exercises. Record versions; use the stable Rust toolchain and edition 2024 for new coursework packages.
- Create your own day01 binary that prints a tool name, a lab-only purpose, and a version label on separate lines. No dependencies or live traffic.
- Locate Cargo.toml, src/main.rs, Cargo.lock and target; describe which files you would commit. Keep generated target contents out of version control.

## Experiment

Run once from the package directory and once from its parent. Explain the different result. Use `cargo run --manifest-path <package>/Cargo.toml` to identify the package explicitly; replace the placeholder with its real relative path.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- The executable prints your chosen three lines.
- You can recover from a compiler error without deleting the project.
- A short environment note includes OS, CPU architecture and exact tool versions.

## Optional Python companion

Print the same three facts in a short Python script. Compare how each language starts execution, without translating Cargo concepts into nonexistent Python equivalents.

## Stretch and reflection

Run `cargo check` and `cargo build`; explain what each produces. Read the official installation page before changing an existing system-wide toolchain.

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-1) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 2](day02.md)
