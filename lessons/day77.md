# Day 77 — Week 11 Review — BACnet wire explorer

[Previous: Day 76](day76.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 78](day78.md)

**Week 11 review · 2–4 hours, split across sessions as needed.** Prerequisites: Days 1–76, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Project brief

Build a Rust CLI that performs bounded discovery and selected read-only property requests using a pinned rusty-bacnet revision. Pair it with your offline BVLC/NPDU/APDU inspector. The goal is to explain the wire and public stack APIs, not to implement an entire BACnet application stack.

Environment: Offline fixtures first; isolated BACnet peers for live evidence. No occupied building network. Apply the [review rubric](LAB_GUIDE.md#review-rubric). This page intentionally contains no worked solution, implementation sequence, or companion implementation. Pick your own decomposition. You may consult language/API references and your earlier work.

## Acceptance criteria

- Keep device instance, object/property identifiers, transport endpoint and BACnet network address distinct.
- Decode the declared packet subset with strict length checks and explicit unsupported cases.
- Correlate at least one confirmed request with success or a named protocol failure.
- Use an independent endpoint or fixture source and record exact versions.
- Bound discovery, outstanding requests and result storage.

## Deliverables

- Rust CLI/inspector source, lockfile and malformed-input tests.
- An annotated discovery exchange and property transaction, or clearly labeled offline equivalents.
- A source map showing which upstream components own service, encoding and transport work.

Label every result **observed**, **fixture-only**, or **not run**. A failed case with a clear explanation is better evidence than an unsupported pass. Keep the baseline within the declared limits before attempting extensions.

## Self-review

- Which bytes would an NPDU router need to inspect, and which belong to application endpoints?
- What remains unproven if only two programs using the same stack have talked to each other?

Explain your choices without reading your source aloud. If a criterion is missing, record a specific next experiment; do not silently redefine completion. Reference material is in [the reading list](SOURCES.md#week-11); references may contain examples, so attempt the review independently first.

[Previous: Day 76](day76.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 78](day78.md)
