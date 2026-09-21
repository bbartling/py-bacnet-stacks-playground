# Day 70 — Week 10 Review — Modbus bench toolkit

[Previous: Day 69](day69.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 71](day71.md)

**Week 10 review · 2–4 hours, split across sessions as needed.** Prerequisites: Days 1–69, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Project brief

Package your Rust Modbus work into a read-only bench CLI with TCP register polling and offline TCP/RTU inspection. The supported subset is explicit: function 03, a bounded quantity, and documented response/error handling. No write function or live serial gateway is required.

Environment: Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Apply the [review rubric](LAB_GUIDE.md#review-rubric). This page intentionally contains no worked solution, implementation sequence, or companion implementation. Pick your own decomposition. You may consult language/API references and your earlier work.

## Acceptance criteria

- Validate MBAP framing, transaction/unit/function correlation, quantity and response byte count.
- Handle exception replies, split/coalesced input, malformed length, stale ID and disconnect.
- Preserve raw registers beside optional configured interpretation.
- Verify offline RTU CRC and explain why it is absent from TCP ADUs.
- Interoperate with an independent peer and respect a finite polling budget.

## Deliverables

- Rust source, CLI usage, lockfile and known-answer/negative tests.
- Normal and exception captures, plus timeout and malformed-peer evidence.
- A scope statement separating offline serial decoding from physical RTU validation.

Label every result **observed**, **fixture-only**, or **not run**. A failed case with a clear explanation is better evidence than an unsupported pass. Keep the baseline within the declared limits before attempting extensions.

## Self-review

- Which fields would a TCP-to-RTU gateway translate or preserve?
- What would make automatic retry of a write risky?

Explain your choices without reading your source aloud. If a criterion is missing, record a specific next experiment; do not silently redefine completion. Reference material is in [the reading list](SOURCES.md#week-10); references may contain examples, so attempt the review independently first.

[Previous: Day 69](day69.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 71](day71.md)
