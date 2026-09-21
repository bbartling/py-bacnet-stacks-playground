# Day 42 — Week 6 Review — offline packet inspector

[Previous: Day 41](day41.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 43](day43.md)

**Week 6 review · 2–4 hours, split across sessions as needed.** Prerequisites: Days 1–41, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Project brief

Build a bounded offline inspector for Ethernet, the selected IPv4/IPv6 subsets, UDP and basic TCP. Use a maintained capture-container reader; the assignment is packet interpretation, not inventing a PCAPNG implementation. Start with [synthetic packet fixtures](fixtures/README.md), then compare with a real capture you are allowed to inspect.

Environment: Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Apply the [review rubric](LAB_GUIDE.md#review-rubric). This page intentionally contains no worked solution, implementation sequence, or companion implementation. Pick your own decomposition. You may consult language/API references and your earlier work.

## Acceptance criteria

- Dispatch using the capture link type and report unsupported types explicitly.
- Respect captured lengths, protocol lengths, VLAN offsets, IPv4 IHL and TCP data offset.
- Identify fragments and unsupported IPv6 chains without fabricated transport fields.
- Handle malformed and truncated fixtures without panics or unbounded allocation.
- Agree with independently checked fields for at least one IPv4 and one IPv6 packet; state checksum limitations.

## Deliverables

- Rust CLI, Cargo.lock, supported-subset document and negative tests.
- Exact fixture/capture provenance plus a field comparison against Wireshark or another independent decoder.
- A maximum file/record/extension policy and evidence that it is enforced.

Label every result **observed**, **fixture-only**, or **not run**. A failed case with a clear explanation is better evidence than an unsupported pass. Keep the baseline within the declared limits before attempting extensions.

## Self-review

- What would be required before advertising full packet reassembly?
- How can a correctly decoded field still be misleading because of where the capture was taken?

Explain your choices without reading your source aloud. If a criterion is missing, record a specific next experiment; do not silently redefine completion. Reference material is in [the reading list](SOURCES.md#week-6); references may contain examples, so attempt the review independently first.

[Previous: Day 41](day41.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 43](day43.md)
