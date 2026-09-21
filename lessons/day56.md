# Day 56 — Week 8 Review — TCP record service

[Previous: Day 55](day55.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 57](day57.md)

**Week 8 review · 2–4 hours, split across sessions as needed.** Prerequisites: Days 1–55, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Project brief

Implement the [bounded record service](WIRE_FORMATS.md#tcp-record-service) in Rust. Clients store and retrieve small opaque values by short keys over a length-prefixed protocol. Keep the store in memory and support the documented command subset only. This is a networking/framing project, not a database design assignment.

Environment: Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Apply the [review rubric](LAB_GUIDE.md#review-rubric). This page intentionally contains no worked solution, implementation sequence, or companion implementation. Pick your own decomposition. You may consult language/API references and your earlier work.

## Acceptance criteria

- Decode every valid split/coalesced message sequence identically.
- Bound frame size, key/value size, stored records and concurrent clients as specified.
- Handle malformed commands, missing keys, slow peers, half-close and premature EOF.
- Keep framing errors distinct from valid application error responses.
- Perform a clean bounded shutdown with useful final counters.

## Deliverables

- Rust client/server source, protocol tests and CLI help.
- A transcript or capture from a second implementation/process; Python is optional.
- Evidence for partial reads, two frames in one read, overload and a disconnect halfway through a frame.

Label every result **observed**, **fixture-only**, or **not run**. A failed case with a clear explanation is better evidence than an unsupported pass. Keep the baseline within the declared limits before attempting extensions.

## Self-review

- What would fail if you assumed one read equals one command?
- Which operations are idempotent, and which timeout outcomes are ambiguous to a client?

Explain your choices without reading your source aloud. If a criterion is missing, record a specific next experiment; do not silently redefine completion. Reference material is in [the reading list](SOURCES.md#week-8); references may contain examples, so attempt the review independently first.

[Previous: Day 55](day55.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 57](day57.md)
