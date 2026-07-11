# Day 71 – DISTINCT, ORDER BY, LIMIT in Rust

## Goal

Query hygiene: dedupe results, sort, cap row count—like SPARQL post-processing in application code.

## Concept

```rust
fn select_distinct_sorted(mut ids: Vec<String>) -> Vec<String> {
    ids.sort();
    ids.dedup();
    ids.truncate(10);
    ids
}
```

Apply after pattern match functions from Days 63–70.

## Why This Matters

UI and agent tools need **top-k** points, not 10k triple dumps.

## Mini Examples

- LIMIT 5 points for dashboard card.
- ORDER BY IRI for stable CLI output.

## Micro Exercises

1. Wrap Day 63 query with distinct + limit flags.
2. Benchmark naive vs sorted dedupe on 1k fake triples (optional).
3. Document why DISTINCT matters after UNION.

## Key Takeaway

**Practical query engines add SQL-like polish**—even hand-rolled Rust matchers.

---

## Python companion — distinct / sort / limit

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
# Post-process polish—Rust track wraps real graph queries.
ids = ["ex:OAT", "ex:SAT", "ex:SAT", "ex:MAT"]
out = sorted(set(ids))[:2]  # DISTINCT + ORDER BY + LIMIT
print(out)
```

| Rust (main lesson) | Python |
|--------|--------|
| `sort` / `dedup` / `truncate` | `sorted(set(...))[:n]` |
| Top-k for UI/agents | same hygiene idea |

**Takeaway:** DISTINCT/ORDER/LIMIT are list hygiene after matching—Python shows it; Rust applies it to query results.
