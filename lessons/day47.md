# Day 47 — Discovery with stable identity and expiry

[Previous: Day 46](day46.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 48](day48.md)

**Week 7 · 45–90 minutes.** Prerequisites: Days 1–46, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Goal

Build bounded peer discovery for your teaching protocol.

## Before you start

Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Follow [workspace and evidence conventions](LAB_GUIDE.md). Save today's work as `student-work/day47/` or in your own learning repository. Record the toolchain; commands and dependency behavior may differ across OS releases. Complete the baseline before the stretch.

## Concept

Discovery produces observations that can be duplicated, delayed or stale. A transport endpoint tells you where a reply came from; a protocol peer ID tells you which identity it claims. Neither is an authentication guarantee. Keep a finite collection window and a maximum peer count, and report conflicts rather than letting the last packet silently rewrite identity.

## Tiny example

An observation record can contain `peer_id`, `source_endpoint`, `last_seen`, and `request_id`. This is networking state, not an ontology or permanent asset database.

Use this to explore the mechanism. It is deliberately smaller than the assignment.

## Coding challenge

- Use the [field messenger contract](WIRE_FORMATS.md#field-messenger) to request status from an explicit list of lab peers; broadcast discovery is optional after Day 45.
- Deduplicate by peer ID within a two-second window, limit results to 32, and report conflicting endpoint claims.
- Track monotonic age for expiry; preserve raw observation counts separately from unique peers.

## Experiment

Run two peers, repeat one reply, then make two endpoints claim the same ID. Predict unique count and conflict reporting.

Write your prediction before running the experiment, then record what changed and why. Use the [capture guide](lab-scripts/wireshark_filters.md) when packets are involved; for offline work, preserve input bytes and actual output instead.

## Acceptance checks

- Duplicate replies do not inflate device count.
- The collection window closes even while replies continue.
- Conflicting identity is visible.

## Optional Python companion

Optionally run one independent responder with a fixed ID to exercise cross-language interoperability.

## Stretch and reflection

Why would a device ID alone be inadequate for trusting a configuration write?

Save the source, relevant test output, and a short explanation of one failure you understand better now. Consult [this week's primary references](SOURCES.md#week-7) for exact API and protocol details. Live interop and hardware steps are learner-run labs, not results claimed by this document.

[Previous: Day 46](day46.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 48](day48.md)
