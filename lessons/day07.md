# Day 07 — Week 1 mini milestone — bench inventory

[Previous: Day 6](day06.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 8](day08.md)

**Week 1 review · 2–4 hours, split across sessions as needed.** Prerequisites: Days 1–6, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Project brief

Create a small offline inventory display using only the language features you have learned. Model a list of lab endpoint labels and a few numeric settings. This is a programming consolidation exercise, not a discovery scanner. Implement this milestone in Rust; existing Python work may serve as a comparison.

Environment: Offline: terminal, Rust; Python is optional. No network device required. Apply the [review rubric](LAB_GUIDE.md#review-rubric). This page intentionally contains no worked solution, implementation sequence, or companion implementation. Pick your own decomposition. You may consult language/API references and your earlier work.

## Acceptance criteria

- Print a readable inventory with explicit units for numeric settings.
- Demonstrate an empty inventory and a missing element without a crash.
- Reject at least one invalid numeric setting and accept a boundary value.
- Use named values rather than one giant hard-coded output string.

## Deliverables

- Source and a short transcript covering normal, empty and invalid input.
- Three sentences distinguishing text labels, numeric policy, and real network discovery.

Label every result **observed**, **fixture-only**, or **not run**. A failed case with a clear explanation is better evidence than an unsupported pass. Keep the baseline within the declared limits before attempting extensions.

## Self-review

- Which invalid states can the compiler catch, and which still need runtime checks?
- What would a person need to know before trusting this output on an actual network?

Explain your choices without reading your source aloud. If a criterion is missing, record a specific next experiment; do not silently redefine completion. Reference material is in [the reading list](SOURCES.md#week-1); references may contain examples, so attempt the review independently first.

[Previous: Day 6](day06.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 8](day08.md)
