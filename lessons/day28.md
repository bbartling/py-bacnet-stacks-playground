# Day 28 — Week 4 Review — Rust field-tool starter kit

[Previous: Day 27](day27.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 29](day29.md)

**Week 4 review · 2–4 hours, split across sessions as needed.** Prerequisites: Days 1–27, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Project brief

Build an offline endpoint-validation CLI that can become the configuration front end for later networking tools. Input is one `label,transport,socket-address` record per line, without quoting. Allowed transports are UDP and TCP; endpoint addresses use standard IPv4 or bracketed IPv6 socket notation. No DNS resolution or live sockets are required.

Environment: Offline: terminal, Rust; Python is optional. No network device required. Apply the [review rubric](LAB_GUIDE.md#review-rubric). This page intentionally contains no worked solution, implementation sequence, or companion implementation. Pick your own decomposition. You may consult language/API references and your earlier work.

## Acceptance criteria

- Accept at most 128 records and 64 KiB input; reject empty labels, unknown transports, invalid addresses and explicit port zero.
- Print a deterministic report of accepted endpoints and line-specific failures. Publish strict vs partial-success behavior.
- Provide help, meaningful exit status, and clean machine output distinct from diagnostics.
- Handle empty, duplicate, malformed and oversized input; document the duplicate policy.
- Demonstrate ownership with no unexplained clones and no panics on untrusted input.

## Deliverables

- Source, Cargo.lock, usage examples and relevant unit/integration test results.
- An independent CLI/input check (Rust, a shell harness or optional Python) and a brief explanation of one error boundary.
- A list of deferred features: this tool validates configuration; it does not prove reachability.

Label every result **observed**, **fixture-only**, or **not run**. A failed case with a clear explanation is better evidence than an unsupported pass. Keep the baseline within the declared limits before attempting extensions.

## Self-review

- Can a syntactically valid address still be unusable on this host?
- Which component owns the original input buffer and the accepted endpoints?

Explain your choices without reading your source aloud. If a criterion is missing, record a specific next experiment; do not silently redefine completion. Reference material is in [the reading list](SOURCES.md#week-4); references may contain examples, so attempt the review independently first.

[Previous: Day 27](day27.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 29](day29.md)
