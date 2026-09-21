# Day 19 — Week 3 Review Project — file-to-report tool

[Previous: Day 18](day18.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 20](day20.md)

**Week 3 review · 2–4 hours, split across sessions as needed.** Prerequisites: Days 1–18, or equivalent skills. Reuse your earlier work rather than start every tool again.

## Project brief

Produce a command-line summary of a small sensor-reading file. Preserve the spirit of your original Day 19 project: files, functions, modules and useful failure handling. Implement the project in Rust. If you already completed the original Python Day 19, keep that credit and use Day 20 as your Rust transition. Input is restricted unquoted `name,value` text with one finite numeric value per record. The public fixtures are in [fixtures/day19](fixtures/day19/README.md). The format deliberately does not support quoted commas.

Environment: Offline: terminal, Rust; Python is optional. No network device required. Apply the [review rubric](LAB_GUIDE.md#review-rubric). This page intentionally contains no worked solution, implementation sequence, or companion implementation. Pick your own decomposition. You may consult language/API references and your earlier work.

## Acceptance criteria

- Report count, minimum, maximum and mean over accepted values; retain each reading label.
- An empty input produces an explicit no-data result, not a zero average or division error.
- Reject malformed field counts, empty names and non-finite values; document strict vs skip-invalid behavior.
- A missing file, invalid UTF-8 and an oversized file (limit 64 KiB) have clear diagnostics and a meaningful exit status.
- Separate reusable processing from terminal output and preserve the input file.

## Deliverables

- Your own source, usage instructions and test/transcript evidence for valid, empty, missing and malformed inputs.
- A brief explanation of the error policy and which statistics were actually computed.
- Keep this implementation intact: Day 20 uses it as the behavior baseline.

Label every result **observed**, **fixture-only**, or **not run**. A failed case with a clear explanation is better evidence than an unsupported pass. Keep the baseline within the declared limits before attempting extensions.

## Self-review

- Could another program reuse the calculations without scraping your terminal output?
- How would a mixed temperature/humidity file make a mathematically correct average misleading? The exercise tests mechanics, not valid aggregation across units.

Explain your choices without reading your source aloud. If a criterion is missing, record a specific next experiment; do not silently redefine completion. Reference material is in [the reading list](SOURCES.md#week-3); references may contain examples, so attempt the review independently first.

[Previous: Day 18](day18.md) · [Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md) · [Next: Day 20](day20.md)
