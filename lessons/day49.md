# Day 49 — Week 7 Review — UDP field messenger

[Previous: Day 48](day48.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 50](day50.md)

**Week 7 review · 2–4 hours, split across sessions as needed.** Prerequisites: Days 1–48, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Project brief

Build a Rust CLI that discovers a bounded set of lab peers and requests their status using [the field messenger wire contract](WIRE_FORMATS.md#field-messenger). Interoperate with another process; it may be Rust or an optional independent Python peer. Keep this a small read-only application protocol.

Environment: Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Apply the [review rubric](LAB_GUIDE.md#review-rubric). This page intentionally contains no worked solution, implementation sequence, or companion implementation. Pick your own decomposition. You may consult language/API references and your earlier work.

## Acceptance criteria

- Validate version, message kind, lengths, ID and peer correlation before accepting a response.
- Finish discovery within two seconds and keep at most 32 peers; disclose conflicts and truncation.
- Bound retries and transaction lifetime despite unrelated or malformed traffic.
- Handle loss, delay and duplicate replies without double completion.
- Support a controlled stop and leave no responder/relay running.

## Deliverables

- CLI source, usage and protocol tests, including wrong-ID and wrong-peer cases.
- Normal and fault captures or simulator logs with a recorded schedule.
- A short report separating observations, unique identities, timeouts and errors.

Label every result **observed**, **fixture-only**, or **not run**. A failed case with a clear explanation is better evidence than an unsupported pass. Keep the baseline within the declared limits before attempting extensions.

## Self-review

- Which operations could be retried safely if you later add writes?
- What evidence would prove the same behavior on a second physical host?

Explain your choices without reading your source aloud. If a criterion is missing, record a specific next experiment; do not silently redefine completion. Reference material is in [the reading list](SOURCES.md#week-7); references may contain examples, so attempt the review independently first.

[Previous: Day 48](day48.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 50](day50.md)
