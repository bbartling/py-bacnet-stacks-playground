# Day 16 — Modules and responsibility boundaries

[Previous: Day 15](day15.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 17](day17.md)

**Week 3 · 45–90 minutes.** Prerequisites: Days 1–15, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Separate reusable logic from the command-line entry point.

## Before you start

Offline: terminal, Rust; Python is optional. No network device required. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day16/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A Rust module groups related code and controls visibility with `pub`. A crate is a compilation unit; a Cargo package may contain more than one crate. Keep these terms distinct. Network applications benefit when codecs can be exercised without starting a process or binding a port. A small module boundary today grows into the separation between router-core, adapter and daemon later.

## Tiny example

In a scratch package, put `pub fn label() -> &'static str { "demo" }` in `src/banner.rs`. Declare `mod banner;` in main.rs and print `banner::label()`. The string literal has static storage; this example does not introduce owned runtime text.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Move your Day 15 calculation into a module with a small public interface.
- Keep argument collection and printing in main.rs. Do not make every helper public.
- Add a module-level description explaining what depends on I/O and what can run offline.

## Experiment

Remove `pub` from the function used by main and read the visibility diagnostic. Restore only the visibility actually required.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- The package builds from its root.
- Main calls a module rather than duplicating its logic.
- An internal helper can remain private.

## Optional Python companion

Split the same responsibility between an imported Python module and a guarded main entry point.

## Stretch and reflection

Explore src/lib.rs and an integration test. What changes when another crate is the caller?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-3) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 15](day15.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 17](day17.md)
