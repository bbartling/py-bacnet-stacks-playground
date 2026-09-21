# Day 75 — Read the rusty-bacnet workspace

[Previous: Day 74](day74.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 76](day76.md)

**Week 11 · 45–90 minutes.** Prerequisites: Days 1–74, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Use the actual pinned upstream public APIs for one Rust discovery experiment.

## Before you start

Offline fixtures first; isolated BACnet peers for live evidence. No occupied building network. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day75/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

An actively developed stack can change APIs faster than a course. The destination appliance records an audited upstream revision; study that revision first and keep its lockfile intact. Separate types, encoding, transport, network and endpoint/service responsibilities by inspecting the workspace instead of assuming crate names imply stable APIs. Student codecs are for learning and tests, not replacements inside the appliance.

## Tiny example

From the destination repo, read `config/upstream-lock.toml` and `Cargo.toml`. In an independent upstream checkout at that revision, use `cargo metadata --no-deps --format-version 1` and `rg "WhoIs|Who-Is|who_is" examples crates` to locate real entry points.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Create a separate Rust coursework package using public APIs from the selected revision. Record repository URL, full commit and toolchain.
- Run or adapt the smallest upstream discovery example on loopback-separated peers or an isolated LAN. Bound discovery duration and results.
- Trace the API path from your call into encoding/transport; do not paste stack internals into your project to avoid an API mismatch.

## Experiment

Compare one discovery result with an independent peer and a PCAP. If live setup is unavailable, compile the selected example and label the packet exercise fixture-only.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- The dependency pin is explicit and reproducible.
- Observed discovery is distinguished from merely compiling.
- No claim about segmentation, BBMD or serial support is inferred from a README alone.

## Optional Python companion

Optional bacpypes3 acts as the external oracle on a separate bind address; Rust remains the client under study.

## Stretch and reflection

How would you evaluate a newer upstream revision without silently changing the appliance pin?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-11) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 74](day74.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 76](day76.md)
