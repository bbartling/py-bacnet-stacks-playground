> **Optional older reference material.** The active Rust networking course is [Days 1–112](../../INDEX.md). Historical day numbers and example commands below are not the current syllabus; inspect code and configuration before use. This material may contain implementation spoilers.

# graph-export (Days 66, 68, 75)

Loads [../model/ahu1.ttl](../model/ahu1.ttl), counts triple lines, writes merged export. Extend on Day 68 with live BACnet → literal triples.

```bash
cargo test
cargo run -- --ttl ../model/ahu1.ttl --out merged.ttl --stub-pv 72.5
```

Lesson: [current course](../../INDEX.md)
