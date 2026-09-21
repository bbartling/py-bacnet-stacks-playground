# Day 92 — Deploy Rust tools to a Raspberry Pi

[Previous: Day 91](day91.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 93](day93.md)

**Week 14 · 45–90 minutes.** Prerequisites: Days 1–91, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Move a known tool onto a Pi while recording enough information to reproduce the build.

## Before you start

Dedicated Pi lab or the explicitly labeled VM/offline alternative. Hardware results must come from the actual hardware. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day92/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

A working host executable is not automatically runnable on a Pi: architecture, target ABI and linked libraries matter. Native compilation is the simplest baseline when resources allow. Cross-compilation requires a matching linker/sysroot and dependency support, not just selecting a Rust target. Deployment also needs a service user, configuration path, logs and an orderly stop.

## Tiny example

Inspect `uname -m`, `cat /etc/os-release`, and the target binary with `file`. Record the source commit and `rustc -Vv`. Use your own course binary name rather than copying a guessed executable path.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Build one completed Rust CLI on the Pi or with a documented compatible cross toolchain.
- Run its offline tests/fixtures and a loopback request before exposing it to another host.
- Write a deployment note covering binary, config, service user, listening address and stop command.

## Experiment

Reboot only your dedicated lab Pi after saving work, then confirm whether the tool should start automatically or manually under your documented policy.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Architecture and ABI match the Pi OS.
- The deployed version is identifiable.
- Remote reachability is not assumed from a successful local run.

## Optional Python companion

Optional Python on the laptop acts as a remote client; installing Python on the appliance is not required.

## Stretch and reflection

What changes when you ship a Buildroot image instead of a binary onto a general-purpose Pi OS?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-14) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 91](day91.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 93](day93.md)
