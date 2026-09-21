# Day 91 — Week 13 Review — two-network BACnet routing bench

[Previous: Day 90](day90.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 92](day92.md)

**Week 13 review · 2–4 hours, split across sessions as needed.** Prerequisites: Days 1–90, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Project brief

Demonstrate BACnet NPDU routing between distinct BACnet networks over two B/IP ports using pinned upstream APIs. The preferred evidence uses isolated interfaces/namespaces and an independent client. A socket-only fallback must be labeled as such and cannot prove broadcast/interface behavior.

Environment: Offline fixtures first; isolated BACnet peers for live evidence. No occupied building network. Apply the [review rubric](LAB_GUIDE.md#review-rubric). This page intentionally contains no worked solution, implementation sequence, or companion implementation. Pick your own decomposition. You may consult language/API references and your earlier work.

## Acceptance criteria

- Declare both BACnet network numbers and all IP addresses/interfaces separately.
- Complete a read-only request through the router and correlate both-side captures.
- Exercise network-message handling and at least one bounded broadcast case.
- Show unavailable-route and hop-exhaustion behavior without a loop or unbounded traffic.
- Explain why BBMD, IP forwarding and this NPDU forwarder solve different problems.

## Deliverables

- Reproducible topology/config, Rust harness or CLI, versions and relevant tests.
- Captures with matching APDU/invoke context, changed headers and actual egress interfaces.
- A failure report and explicit exclusions such as BBMD/FDR, IPv6 or physical MS/TP if untested.

Label every result **observed**, **fixture-only**, or **not run**. A failed case with a clear explanation is better evidence than an unsupported pass. Keep the baseline within the declared limits before attempting extensions.

## Self-review

- Could a direct path have bypassed the router in your successful experiment? How did you rule it out?
- Which evidence must be repeated when moving from host-built code to an appliance image?

Explain your choices without reading your source aloud. If a criterion is missing, record a specific next experiment; do not silently redefine completion. Reference material is in [the reading list](SOURCES.md#week-13); references may contain examples, so attempt the review independently first.

[Previous: Day 90](day90.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 92](day92.md)
