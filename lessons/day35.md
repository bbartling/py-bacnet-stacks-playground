# Day 35 — Week 5 Review — network detective

[Previous: Day 34](day34.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 36](day36.md)

**Week 5 review · 2–4 hours, split across sessions as needed.** Prerequisites: Days 1–34, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Project brief

Investigate three deliberately limited cases: a wrong IPv4 prefix, a missing or wrong next hop, and a name-resolution failure. Add an IPv6 case that distinguishes missing link scope from an unavailable service. Use a disposable topology or supplied offline route/address cases, never reconfigure the workstation carrying your remote session.

Environment: Linux loopback / offline packet fixtures; use a disposable VM for privileged network experiments. Apply the [review rubric](LAB_GUIDE.md#review-rubric). This page intentionally contains no worked solution, implementation sequence, or companion implementation. Pick your own decomposition. You may consult language/API references and your earlier work.

## Acceptance criteria

- Use your Rust prefix/route/endpoint tools to make a prediction before consulting OS results.
- Explain source/destination IP, next hop, neighbor MAC and interface scope where applicable.
- Separate DNS success, packet delivery and application availability.
- Identify which OS facts your simplified route model omits.
- For live work, collect a relevant ARP/NDP/ICMP/DNS trace; for offline work, label the evidence accordingly.

## Deliverables

- A topology with prefixes, gateways and interfaces; tool source and relevant tests.
- A case table with symptom, prediction, evidence, diagnosis and one validating experiment.
- Capture frame references or exact offline inputs, plus limitations.

Label every result **observed**, **fixture-only**, or **not run**. A failed case with a clear explanation is better evidence than an unsupported pass. Keep the baseline within the declared limits before attempting extensions.

## Self-review

- Which diagnosis would be wrong if a firewall silently dropped traffic?
- What additional evidence would distinguish a cached DNS response from no attempted lookup?

Explain your choices without reading your source aloud. If a criterion is missing, record a specific next experiment; do not silently redefine completion. Reference material is in [the reading list](SOURCES.md#week-5); references may contain examples, so attempt the review independently first.

[Previous: Day 34](day34.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 36](day36.md)
