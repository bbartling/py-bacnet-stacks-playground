# Day 84 — Week 12 Review — BACnet transaction lab

[Previous: Day 83](day83.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 85](day85.md)

**Week 12 review · 2–4 hours, split across sessions as needed.** Prerequisites: Days 1–83, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Project brief

Build a robust read-only Rust collector plus a segmentation evidence notebook. Use public pinned stack APIs for real transactions and a separate bounded model for segmentation event tests. Optional COV/write exercises support understanding, but the submitted collector does not need a write path.

Environment: Offline fixtures first; isolated BACnet peers for live evidence. No occupied building network. Apply the [review rubric](LAB_GUIDE.md#review-rubric). This page intentionally contains no worked solution, implementation sequence, or companion implementation. Pick your own decomposition. You may consult language/API references and your earlier work.

## Acceptance criteria

- Limit outstanding requests, retry ownership, response memory and transaction lifetime.
- Preserve per-property errors and distinguish timeout from protocol failure.
- Demonstrate duplicate/late-response handling and cancellation in an offline deterministic harness.
- Explain a segmented APDU trace, including wraparound and missing-segment evidence under the declared model.
- State actual stack/peer support and avoid claiming conformance from simulator success.

## Deliverables

- Rust collector and event-harness source, lockfile, supported-feature table and tests.
- A normal read capture plus a timeout/error trace or labeled fixture.
- Three separate explanations of IP fragmentation, TCP segmentation and BACnet APDU segmentation.

Label every result **observed**, **fixture-only**, or **not run**. A failed case with a clear explanation is better evidence than an unsupported pass. Keep the baseline within the declared limits before attempting extensions.

## Self-review

- Could a wrapper retry loop multiply the stack retry count?
- What must remain an endpoint responsibility when traffic crosses a BACnet router?

Explain your choices without reading your source aloud. If a criterion is missing, record a specific next experiment; do not silently redefine completion. Reference material is in [the reading list](SOURCES.md#week-12); references may contain examples, so attempt the review independently first.

[Previous: Day 83](day83.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 85](day85.md)
