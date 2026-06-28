## Day 71 – DISTINCT, ORDER BY, LIMIT in Rust

### Goal

Query hygiene: dedupe results, sort, cap row count—like SPARQL post-processing in application code.

### Concept

```rust
fn select_distinct_sorted(mut ids: Vec<String>) -> Vec<String> {
    ids.sort();
    ids.dedup();
    ids.truncate(10);
    ids
}
```

Apply after pattern match functions from Days 63–70.

### Why This Matters

UI and agent tools need **top-k** points, not 10k triple dumps.

### Mini examples

- LIMIT 5 points for dashboard card.
- ORDER BY IRI for stable CLI output.

### Micro exercises

1. Wrap Day 63 query with distinct + limit flags.
2. Benchmark naive vs sorted dedupe on 1k fake triples (optional).
3. Document why DISTINCT matters after UNION.

### Key takeaway

**Practical query engines add SQL-like polish**—even hand-rolled Rust matchers.
