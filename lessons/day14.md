# Day 14 — Week 2 mini milestone — bounded event reporter

[Previous: Day 13](day13.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 15](day15.md)

**Week 2 review · 2–4 hours, split across sessions as needed.** Prerequisites: Days 1–13, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Project brief

Build an offline report from a finite collection of endpoint observations and status events. Use loops, validation, collections and a deliberate identity rule. Make it useful enough that a future socket program could feed it observations, while keeping networking out of this assignment.

Environment: Offline: terminal, Rust; Python is optional. No network device required. Apply the [review rubric](LAB_GUIDE.md#review-rubric). This page intentionally contains no worked solution, implementation sequence, or companion implementation. Pick your own decomposition. You may consult language/API references and your earlier work.

## Acceptance criteria

- Report accepted records, rejected records, event totals and distinct identities separately.
- Limit processing to a declared maximum and disclose omitted records.
- Produce deterministic output for the same accepted observations.
- Handle empty input, duplicate identities, an unknown event and a malformed record.

## Deliverables

- Source and a normal/failure transcript with the input alongside it.
- A short description of your identity key and what information deduplication discards.

Label every result **observed**, **fixture-only**, or **not run**. A failed case with a clear explanation is better evidence than an unsupported pass. Keep the baseline within the declared limits before attempting extensions.

## Self-review

- Which parts should remain unchanged when events eventually come from UDP?
- Can the summary distinguish a repeated response from a second device? What is missing?

Explain your choices without reading your source aloud. If a criterion is missing, record a specific next experiment; do not silently redefine completion. Reference material is in [the reading list](SOURCES.md#week-2); references may contain examples, so attempt the review independently first.

[Previous: Day 13](day13.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 15](day15.md)
