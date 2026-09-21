# Day 74 — APDU types, invoke IDs and tags

[Previous: Day 73](day73.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 75](day75.md)

**Week 11 · 45–90 minutes.** Prerequisites: Days 1–73, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Decode a small service subset without confusing APDU headers with tagged parameters.

## Before you start

Offline fixtures first; isolated BACnet peers for live evidence. No occupied building network. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day74/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

BACnet APDUs have different layouts for confirmed requests, unconfirmed requests, acknowledgements, errors and other outcomes. Invoke IDs correlate confirmed transactions; unconfirmed discovery does not use the same transaction header. BACnet tag headers carry type/context and length/value information, with special handling for some forms. A generic one-byte-tag assumption will break extended lengths and opening/closing tags.

## Tiny example

The supplied Who-Is fixture contains an unconfirmed request with no optional range parameters. Compare its APDU header with a confirmed ReadProperty capture; mark exactly where service parameters begin in each.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Support unconfirmed Who-Is/I-Am recognition and a declared subset of ReadProperty-related APDU headers.
- Build bounded tag inspection for the specific primitive/context forms required by your fixtures; classify unsupported extended forms explicitly.
- Retain raw service bytes and reject incomplete lengths rather than guessing a value.

## Experiment

Truncate a tag payload and substitute a different APDU type while keeping the old bytes. Verify that header selection changes before tag interpretation.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Unconfirmed discovery is not assigned a fabricated invoke ID.
- Unsupported tags are visible rather than silently skipped as known values.
- The supported service subset is written beside the tests.

## Optional Python companion

Optionally cross-check with a pinned independent BACnet implementation.

## Stretch and reflection

Which tag forms would need to be added before decoding arbitrary constructed BACnet values?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-11) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 73](day73.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 75](day75.md)
