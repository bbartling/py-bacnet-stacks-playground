# graph-export (Days 66, 68, 75)

Loads [../model/ahu1.ttl](../model/ahu1.ttl), counts triple lines, writes merged export. Extend on Day 68 with live BACnet → literal triples.

```bash
cargo test
cargo run -- --ttl ../model/ahu1.ttl --out merged.ttl --stub-pv 72.5
```

Lesson: [Day 75](../../day75.md)
