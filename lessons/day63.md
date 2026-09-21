# Day 63 — Week 9 Review — TCP traffic switch

[Previous: Day 62](day62.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 64](day64.md)

**Week 9 review · 2–4 hours, split across sessions as needed.** Prerequisites: Days 1–62, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Project brief

Build a Rust TCP proxy with two configurable listener/backend mappings. Use it to carry your record-service traffic and at least one opaque binary payload. This is the fun “TCP router” project: document that it is a connection proxy, while the Pi project later performs actual IP forwarding.

Environment: Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Apply the [review rubric](LAB_GUIDE.md#review-rubric). This page intentionally contains no worked solution, implementation sequence, or companion implementation. Pick your own decomposition. You may consult language/API references and your earlier work.

## Acceptance criteria

- Validate configuration, cap concurrent sessions, and bound connection/shutdown time.
- Preserve bidirectional bytes and client half-close so EOF-triggered backend responses work.
- Keep one unavailable backend from blocking the other mapping.
- Do not replay partial in-flight streams after failure.
- Expose bounded structured logs and per-direction byte/connection counters.

## Deliverables

- Source, lockfile, config example, CLI help and direct-vs-proxied tests.
- A normal capture plus slow-peer, half-close, unavailable-backend and shutdown evidence.
- A deployment note for a future Pi, including listening interfaces and resource limits.

Label every result **observed**, **fixture-only**, or **not run**. A failed case with a clear explanation is better evidence than an unsupported pass. Keep the baseline within the declared limits before attempting extensions.

## Self-review

- Which transport properties are preserved and which endpoint addresses change?
- How would TLS passthrough affect what this proxy can inspect?

Explain your choices without reading your source aloud. If a criterion is missing, record a specific next experiment; do not silently redefine completion. Reference material is in [the reading list](SOURCES.md#week-9); references may contain examples, so attempt the review independently first.

[Previous: Day 62](day62.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 64](day64.md)
